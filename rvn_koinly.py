#!/usr/bin/env python3

import argparse
import csv
import datetime
import json
import logging
import requests
from decimal import Decimal


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return str(o)
        elif isinstance(o, datetime.datetime):
            return str(o)

        return super(DecimalEncoder, self).default(o)


RVN_BC_EXPLORER = 'https://api.ravencoin.org/api'

parser = argparse.ArgumentParser(
    description="Convert Atomic Wallet CSV export to Koinly"
)
parser.add_argument(
    "-w", "--wallet", dest="wallet", help="RVN public wallet address", required=True
)
parser.add_argument(
    "-o", "--output", dest="output", help="Koinly output CSV file", required=True
)
parser.add_argument(
    "-l", "--log-level", dest="log_level", help="Logging level", default="info"
)
opts = parser.parse_args()
log_level = getattr(logging, opts.log_level.upper())
logging.basicConfig(format='%(levelname)s: %(message)s', level=log_level)

new_csv_data = []
logging.info('Pulling data from %s/txs?address=%s', RVN_BC_EXPLORER, opts.wallet)
txs = requests.get('{}/txs'.format(RVN_BC_EXPLORER), params={'address': opts.wallet, 'pageNum': 0}).json()
logging.debug('Will parse %s page(s) of transactions', txs['pagesTotal'])

for page in range(0, txs['pagesTotal']):
    if page > 0:
        logging.debug('Requesting transactions page %s', page + 1)
        txs = requests.get('{}/txs'.format(RVN_BC_EXPLORER), params={'address': opts.wallet, 'pageNum': page}).json()

    for cur_tx in txs['txs']:
        logging.debug('Found transaction %s: %s', cur_tx['txid'], json.dumps(cur_tx))
        koinly_sent = Decimal(0)
        koinly_received = Decimal(0)
        fee = Decimal(0)
        koinly_date = datetime.datetime.utcfromtimestamp(cur_tx['time'])
        # vin are coins sent out from an address
        for sent in cur_tx['vin']:
            if sent['addr'] == opts.wallet:
                koinly_sent += Decimal(sent['value'])
                fee = Decimal(cur_tx['fees'])

        # vout are coins sent to an address
        for received in cur_tx['vout']:
            if opts.wallet in received['scriptPubKey']['addresses']:
                koinly_received += Decimal(received['value'])

        if koinly_sent > koinly_received:
            logging.debug('Found partial refund for sent funds')
            koinly_sent -= koinly_received
            koinly_received = Decimal(0)

        if fee > 0 and koinly_sent > 0:
            koinly_sent -= fee

        new_data = {
            "Date": koinly_date,
            "Sent Amount": koinly_sent,
            "Sent Currency": 'RVN',
            "Received Amount": koinly_received,
            "Received Currency": 'RVN',
            "Fee Amount": fee,
            "Fee Currency": 'RVN',
            "Net Worth Amount": "",
            "Net Worth Currency": "",
            "Label": "",
            "Description": "",
            "TxHash": cur_tx['txid'],
        }
        logging.debug('CSV details for %s: %s', cur_tx['txid'], json.dumps(new_data, cls=DecimalEncoder))
        new_csv_data.append(new_data)

if new_csv_data:
    csv_columns = new_csv_data[0].keys()
    with open(opts.output, "w") as output:
        output_csv = csv.DictWriter(output, fieldnames=csv_columns)
        output_csv.writeheader()
        for data in new_csv_data:
            output_csv.writerow(data)

    logging.info('Wrote %s transaction(s) to %s', len(new_csv_data), opts.output)
else:
    logging.info('No transactions found for address "%s"', opts.wallet)
