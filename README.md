# Scripts for creating koinly.io CSV imports
[koinly.io](https://koinly.io) is a useful tool for tracking multiple crypto assets in one place.  Unfortunately, it does not support reading from every blockchain (that would be impossible).

The purpose of these scripts is to read from blockchains not supported by Koinly and put all the transactions in the CSV format supported by Koinly.  It is then a simple task to import the CSV in Koinly and track your crypto assets for non-supported blockchains.

## Supported Blockchains
This list will grow as needed.  Any blockchains later supported by Koinly will eventually be removed from this list.

* Ravencoin
* Raptoreum

## Planned Blockchain support
I have no personal need for other blockchain support, but feel free to put in a request via Github issues.

## Known Issues
* Private transactions for RTM will result in some odd looking inputs/outputs in the CSV.  I have found that everything still calculates out correctly, but be aware of this oddity.
* After finding all transactions for a given wallet via ```raptoreum-cli```, transaction details are looked up via the [Raptoreum Blockchain Explorer](https://explorer.raptoreum.com/).  This means it can be a little slow to retrieve transaction information the first time it is needed.  Responses are cached to disk and further requests will be MUCH faster (even across runs of the script).
* The Ravencoin script does not currently implement caching of responses from the blockchain explorer.  As such, it can be a little slow on each run.  This will be added later.

## How to use
These scripts rely on Python 3.4+ to run.  As such, a python interpreter must be installed wherever you run the scripts.  In addition, the required python libraries can be found in the [requirements file](requirements.txt).

For ease of use, it is suggested to use a Python virtual environment to install the necessary dependencies and run the script.

Creating an environment and installing the dependencies can be done like this:
```
virtualenv /path/to/virtualenv
/path/to/virtualenv/bin/pip install -r requirementments.txt
```

After doing the above, the scripts can be run:
```
/path/to/virtualenv/bin/python3 rtm_koinly.py -w <rtm_wallet> -o my_rtm_output.csv
/path/to/virtualenv/bin/python3 rvn_koinly.py -w <rvn_wallet> -o my_rvn_output.csv
```

To see all available options, pass the ```--help``` parameter to the desired script.

### Requirements for rtm_koinly.py
The use of the ```rtm_koinly.py``` requires that ```raptoreumd``` (from the [Raptoreum Wallet](https://raptoreum.com/)) be running.  ```raptoreum-cli``` is then used to find all transactions on a given wallet.

Please wait for ```raptoreumd``` (or the Raptoreum GUI in Windows) to get a complete set of transactions for a given wallet.

## Donations
If you found these scripts helpful and would like to donate to the author, you can do so at the following addresses.  This does not provide any guarantee of future support.

* **ETH:** 0xDcd7c971Fe679569CAeaB8A91f7a1f291B527F21
* **BTC:** 1BPvBqaMjqWVHrmeMQTrZqADZr5n4ML5GA
* **RVN:** RPq85qKtLg8dgrsGPicQrBpLVgR4YU4txg
* **RTM:** RHhkbZf6F4r2usUV2753PaEDanhErSQiqe

## License
Apache License 2.0