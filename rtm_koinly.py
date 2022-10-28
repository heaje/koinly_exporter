#!/usr/bin/env python3

import argparse
import csv
import datetime
import json
import logging
import os
import shlex
import subprocess
import sys
from typing import Optional
from decimal import Decimal

import diskcache
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib3.response import HTTPResponse


class LogRetry(Retry):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def sleep(self, response: Optional["HTTPResponse"] = None) -> None:
        retry_after = self.get_retry_after(response)
        if not retry_after:
            retry_after = self.get_backoff_time()

        logging.info(
            'HTTP %s response when making request.  Will retry after backoff (%s seconds).',
            response.status, retry_after
        )
        super().sleep(response)


class TimeoutHTTPAdapter(HTTPAdapter):
    DEFAULT_TIMEOUT = 5

    def __init__(self, *args, **kwargs):
        self.timeout = self.DEFAULT_TIMEOUT
        if "timeout" in kwargs:
            self.timeout = kwargs["timeout"]
            del kwargs["timeout"]
        super().__init__(*args, **kwargs)

    def send(self, request, **kwargs):
        timeout = kwargs.get("timeout")
        if timeout is None:
            kwargs["timeout"] = self.timeout
        return super().send(request, **kwargs)


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return str(o)
        elif isinstance(o, datetime.datetime):
            return str(o)

        return super(DecimalEncoder, self).default(o)


script_name_no_ext = os.path.basename(os.path.splitext(__file__)[0])
parser = argparse.ArgumentParser(
    description="Convert Atomic Wallet CSV export to Koinly"
)
parser.add_argument("-w", "--wallet", dest="wallet",
                    help="RTM public wallet address", required=True)
parser.add_argument("-o", "--output", dest="output",
                    help="Koinly output CSV file", required=True)
parser.add_argument("-l", "--log-level", dest="log_level",
                    help="Logging level", default="info")
parser.add_argument("-p", "--raptoreum-cli-path", dest="rtm_cli_path",
                    help="Path to the raptoreum-cli command", default="raptoreum-cli")
parser.add_argument("--cache-dir", dest="cache_dir",
                    help="Directory for caching information", default=script_name_no_ext)
parser.add_argument("--http-request-timeout", dest="request_timeout",
                    help="Timeout in seconds for retrieving transaction information", default=5)
parser.add_argument("--http-failure-retry", dest="failure_retry",
                    help="The number of times to retry requests when retrieving transaction information", default=5)
parser.add_argument("--http-backoff-factor", dest="backoff_factor",
                    help="The backoff factor when doing exponential backoff for HTTP requests.", default=10)
opts = parser.parse_args()
log_level = getattr(logging, opts.log_level.upper())
logging.basicConfig(format="%(levelname)s: %(message)s", level=log_level)

CACHE = diskcache.Cache(directory=opts.cache_dir)
RTM_BC_EXPLORER = "https://explorer.raptoreum.com"
retry_strategy = LogRetry(
    total=opts.failure_retry,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["HEAD", "GET", "OPTIONS"],
    backoff_factor=opts.backoff_factor,
)
http = requests.Session()
http.mount("https://", TimeoutHTTPAdapter(max_retries=retry_strategy,
           timeout=opts.request_timeout))
http.mount("http://", TimeoutHTTPAdapter(max_retries=retry_strategy,
           timeout=opts.request_timeout))

try:
    address_deltas_param = {"addresses": [opts.wallet]}
    cmd = shlex.split("{} getaddressdeltas '{}'".format(
        opts.rtm_cli_path, json.dumps(address_deltas_param))
    )
    logging.debug('Running command: %s', cmd)
    result = subprocess.run(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    if result.returncode != 0:
        logging.error(
            'Error when running raptoreum-cli.  Is raptoreumd running?')
        logging.error('Command: %s', ' '.join(cmd))
        logging.error('Response: %s', result.stderr)
        sys.exit(1)
except FileNotFoundError as e:
    logging.error('Cannot find %s (%s)', opts.rtm_cli_path, str(e))
    sys.exit(1)

data_by_tx = {}
try:
    json_result = json.loads(result.stdout)
except json.decoder.JSONDecodeError:
    tmp_result = result.stdout.decode("utf-8").split('main\n', 1)[1]
    json_result = json.loads(tmp_result)

for data in json_result:
    txid = data["txid"]

    cur_tx = CACHE.get(txid)
    if not cur_tx:
        logging.info(
            "Requesting info for transaction from blockchain explorer: %s", txid)
        tx_url = "{}/api/getrawtransaction?txid={}".format(
            RTM_BC_EXPLORER, txid)
        cur_tx = http.get(tx_url)
        cur_tx = cur_tx.json()
        CACHE.set(txid, cur_tx)
    else:
        logging.info("Found transaction in cache: %s", txid)

    koinly_sent = Decimal(0)
    koinly_received = Decimal(0)
    fee = Decimal(0)
    koinly_date = datetime.datetime.utcfromtimestamp(cur_tx["time"])
    tx_amount = data["satoshis"] / 100000000

    if tx_amount > 0:
        koinly_received = abs(Decimal(tx_amount))
    elif tx_amount < 0:
        koinly_sent = abs(Decimal(tx_amount))

    if txid in data_by_tx:
        data_by_tx[txid]["sent"] += koinly_sent
        data_by_tx[txid]["received"] += koinly_received
        data_by_tx[txid]["fee"] += fee
    else:
        data_by_tx[txid] = dict(
            sent=koinly_sent, received=koinly_received, fee=fee, timestamp=koinly_date
        )

new_csv_data = []
for txid, info in data_by_tx.items():
    if info["sent"] > info["received"]:
        logging.debug("Found partial refund for sent funds")
        info["sent"] -= info["received"]
        info["received"] = Decimal(0)

    new_data = {
        "Date": info["timestamp"],
        "Sent Amount": info["sent"],
        "Sent Currency": "RTM",
        "Received Amount": info["received"],
        "Received Currency": "RTM",
        "Fee Amount": info["fee"],
        "Fee Currency": "RTM",
        "Net Worth Amount": "",
        "Net Worth Currency": "",
        "Label": "",
        "Description": "",
        "TxHash": txid,
    }
    logging.debug(
        "CSV details for %s: %s", txid, json.dumps(
            new_data, cls=DecimalEncoder)
    )
    new_csv_data.append(new_data)


if new_csv_data:
    csv_columns = new_csv_data[0].keys()
    with open(opts.output, "w") as output:
        output_csv = csv.DictWriter(output, fieldnames=csv_columns)
        output_csv.writeheader()
        for data in new_csv_data:
            output_csv.writerow(data)

    logging.info("Wrote %s transaction(s) to %s",
                 len(new_csv_data), opts.output)
else:
    logging.info('No transactions found for address "%s"', opts.wallet)
