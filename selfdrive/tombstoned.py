#!/usr/bin/env python3
import os
import time

from raven import Client
from raven.transport.http import HTTPTransport

from selfdrive.version import version, dirty
from selfdrive.swaglog import cloudlog

MAX_SIZE = 100000 * 10  # Normal size is 40-100k, allow up to 1M


def get_tombstones():
  """Returns list of (filename, ctime) for all tombstones in /data/tombstones
  and apport crashlogs in /var/crash"""
  files = []
  for folder in ["/data/tombstones/", "/var/crash/"]:
    if os.path.exists(folder):
      with os.scandir(folder) as d:

        # Loop over first 1000 directory entries
        for _, f in zip(range(1000), d):
          if f.name.startswith("tombstone") or f.name.endswith(".crash"):
            files.append((f.path, int(f.stat().st_ctime)))
  return files


def report_tombstone(fn, client):
  f_size = os.path.getsize(fn)
  if f_size > MAX_SIZE:
    cloudlog.error(f"Tombstone {fn} too big, {f_size}. Skipping...")
    return

  with open(fn, encoding='ISO-8859-1') as f:
    contents = f.read()

  # Get summary for sentry title
  if fn.endswith(".crash"):
    lines = contents.split('\n')
    message = lines[6]

    status_idx = contents.find('ProcStatus')
    if status_idx >= 0:
      lines = contents[status_idx:].split('\n')
      message += " " + lines[1]
  else:
    message = " ".join(contents.split('\n')[5:7])

    # Cut off pid/tid, since that varies per run
    name_idx = message.find('name')
    if name_idx >= 0:
      message = message[name_idx:]

    # Cut off fault addr
    fault_idx = message.find(', fault addr')
    if fault_idx >= 0:
      message = message[:fault_idx]


  cloudlog.error({'tombstone': message})
  client.captureMessage(
    message=message,
    sdk={'name': 'tombstoned', 'version': '0'},
    extra={
      'tombstone_fn': fn,
      'tombstone': contents
    },
  )


def main():
  initial_tombstones = set(get_tombstones())

  client = Client('https://137e8e621f114f858f4c392c52e18c6d:8aba82f49af040c8aac45e95a8484970@sentry.io/1404547',
                  install_sys_hook=False, transport=HTTPTransport, release=version, tags={'dirty': dirty}, string_max_length=10000)

  client.user_context({'id': os.environ.get('DONGLE_ID')})
  while True:
    now_tombstones = set(get_tombstones())


    for fn, ctime in (now_tombstones - initial_tombstones):
      try:
        cloudlog.info(f"reporting new tombstone {fn}")
        report_tombstone(fn, client)
      except Exception:
        cloudlog.exception(f"Error reporting tombstone {fn}")

    initial_tombstones = now_tombstones
    time.sleep(5)


if __name__ == "__main__":
  main()
