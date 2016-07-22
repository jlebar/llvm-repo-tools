#!/usr/local/env python

from __future__ import print_function

import argparse
import os
import subprocess
import sys
import time

OLD_UPSTREAM='old-clang/master'
NEW_UPSTREAM='origin/master'
CACHE_DIR='/tmp/filter-cache'
CACHE_ENABLED=True

try:
  import pyfscache
except ImportError:
  CACHE_ENABLED=False

def cache_decorator(name):
  def wrapper(fn):
    if CACHE_ENABLED:
      CACHE = pyfscache.FSCache('/tmp/filter-branch-cache/%s' % name)
      return CACHE(fn)
    return fn
  return wrapper


def time_decorator(fn):
  def closure(*args, **kw):
    start = time.time()
    ret = fn(*args, **kw)
    end = time.time()
    #print('%r(%r, %r)=%r took: %2.4fs' % (fn.__name__, args, kw, ret, end - start),
    #      file=sys.stderr)
    return ret
  return closure


@cache_decorator('should_edit')
@time_decorator
def should_edit(rev):
  """Determines whether rev is not in OLD_UPSTREAM and thus should be filtered."""
  # If rev is in OLD_UPSTREAM, `git merge-base rev OLD_UPSTREAM` will be rev.
  merge_base = subprocess.check_output(['git', 'merge-base', rev, OLD_UPSTREAM]).strip()
  return merge_base != rev


@cache_decorator('map_to_new_upstream')
@time_decorator
def map_to_new_upstream(rev):
  """Finds a commit in NEW_UPSTREAM corresponding to this commit.

  If we can't find a corresponding commit,
   - if rev is in OLD_UPSTREAM, raises an error;
   - otherwise, returns None.

  Identifies commits according to the tuple (commit time, author email).  This
  is sufficient to uniquely identify a commit in our monorepo.
  """
  date, email = subprocess.check_output(['git', 'show', '-s', '--format=%at %ae', rev]).strip().split(' ', 1)
  new_upstream_revs = subprocess.check_output(
      ['git', 'log', '--author', email, '--since', date, '--until', str(int(date) + 1), '--pretty=%H', NEW_UPSTREAM]
    ).strip().split('\n')
  if len(new_upstream_revs) > 1:
    raise RuntimeError('Revision %s has more than one corresponding rev in new '
                       'upstream, %s.  Maybe (author email, date) is not unique?'
                       % (rev, NEW_UPSTREAM))
  if not new_upstream_revs or not new_upstream_revs[0]:
    # Check if rev is in OLD_UPSTREAM.  If so, it's an error that we couldn't
    # map_to_new_upstream to NEW_UPSTREAM.  Otherwise, we can return None.
    in_old_upstream = subprocess.check_output(
        ['git', 'merge-base', rev, OLD_UPSTREAM]).strip() == rev
    if in_old_upstream:
        raise RuntimeError("Couldn't map_to_new_upstream revision %s from %s to %s."
                           % (rev, OLD_UPSTREAM, NEW_UPSTREAM))
    return None

  return new_upstream_revs[0]


def map_to_filtered(rev):
  """Gets hash of rev after filtering.

  If rev hasn't been filtered (yet), returns None.

  Equivalent to the `map` function exposed by git-filter-branch, except that
  function returns rev if the revision hasn't yet been filtered, and that this
  function raises an error if rev maps to multiple commits.
  """
  #if not workdir:
  #  raise RuntimeError("workdir environment variable is empty?")
  mapfile = '../map/%s' % rev
  try:
    with open(mapfile, 'r') as f:
      lines = f.read().strip().split('\n')
      if len(lines) != 1:
        raise RuntimeError("mapfile %s doesn't contain a single line: %s" % (mapfile, str(lines)))
      return lines[0]
  except IOError:
    return None


# See http://stackoverflow.com/questions/23841111/change-file-name-case-using-git-filter-branch
@time_decorator
def filter_index(rev):
  if not should_edit(rev):
    return

  # Try to find a parent rev that's in OLD_UPSTREAM.  If so, map_to_new_upstream
  # it to NEW_UPSTREAM and use that as our parent below.  Otherwise, pick the
  # first parent; it's as good as any other.
  parents = subprocess.check_output(
      ['git', 'rev-list', '--parents', '-n', '1', rev]).strip().split()[1:]
  parent_rev = parents[0]
  for tp in (map_to_new_upstream(p) for p in parents):
    if tp is None:
      continue
    parent_rev = tp
    break

  # If our parent has already been through git-filter-branch, use the filtered
  # parent.
  filtered_parent_rev = map_to_filtered(parent_rev)
  if filtered_parent_rev:
    parent_rev = filtered_parent_rev

  index_file = os.environ['GIT_INDEX_FILE']
  new_index_file = index_file + '.new'

  # TODO: Parameterize this
  sh_cmd = r"""
    cat <(git ls-tree -r %s | sed -e $'s:\t:\tclang/:') \
        <(git ls-tree -r %s | grep -v $'\tclang/') | \
    GIT_INDEX_FILE=%s git update-index --index-info
  """ % (rev, parent_rev, new_index_file)
  subprocess.check_call(['bash', '-c', sh_cmd])
  os.rename(new_index_file, index_file)


@time_decorator
def filter_parent(rev):
  if not should_edit(rev):
    print(sys.stdin.read())
    return

  new_parents = []
  # -p rev1 -p rev2 -p rev3
  for p in sys.stdin.read().strip().split():
    if p == '-p':
      new_parents.append(p)
      continue
    tp = map_to_new_upstream(p)
    if tp:
      new_parents.append(tp)
    else:
      new_parents.append(p)

  print(' '.join(new_parents))


if __name__ == '__main__':
  rev = os.environ['GIT_COMMIT']
  cmd = sys.argv[1] if len(sys.argv) > 1 else None
  if cmd == 'index':
    filter_index(rev)
  elif cmd == 'parent':
    pass
    filter_parent(rev)
  else:
    print('Usage: %s index|parent' % sys.argv[0])
    sys.exit(1)
