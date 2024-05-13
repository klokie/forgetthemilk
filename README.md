# forgetthemilk

Convert all tasks exported by Remember The Milk in JSON format into a CSV format file or files that Todoist will ingest as a project template.

## dependencies

- Python 3.6+

## installation

- `python -m venv venv && source venv/bin/activate`
- `pip install argparse python-dateutil relativedelta python-dateutil`

## Usage

Usage is dirt simple:

```sh
$ python ./forgetthemilk.py --help
usage: forgetthemilk.py [-h] rtm_json csv_incomplete csv_completed

positional arguments:
  rtm_json        The JSON file you exported from Remember The Milk - required
  csv_incomplete  CSV file to which to write incomplete RTM tasks - optional; defaults to
                  out.csv
  csv_completed   CSV file to which to write completed RTM tasks - optional; defaults to
                  rtm_completed.csv

optional arguments:
  -h, --help  show this help message and exit
```

## Caveats

RTM tasks are imported as active tasks in the current project to which they are imported.

Note that you will need to sign up for pro plan to increase project limit from 5.
Also, mind the limits for 300 active tasks for any given project. This is a limitation of Todoist, and is independent of free vs pro plan.

Labels won't automatically show up in the sidebar. To add them,

1. go to Filters & Labels
2. Find imported labels under the list at the bottom.
3. Click on the label you want to show up in the sidebar. You can add it to "Favorites" to show up in the sidebar.
