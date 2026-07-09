import os, re, glob, py_compile
from collections import defaultdict

EXCLUDE_DIRS = {'.venv','venv','__pycache__','build','dist','.git','.mypy_cache','node_modules','.pytest_cache','oracleJdk-26'}

# Explicit patterns to detect sqlite usage
PATTERNS = [
  ('import sqlite3', re.compile(r'(^|\s)import\s+sqlite3\b')),
  ('from sqlite3', re.compile(r'(^|\s)from\s+sqlite3\b')),
  ('sqlite3.connect', re.compile(r'\bsqlite3\.connect\b')),
  ('sqlite3.Row', re.compile(r'\bsqlite3\.Row\b')),
  ('sqlite3.Cursor', re.compile(r'\bsqlite3\.Cursor\b')),
  ('sqlite3.Error', re.compile(r'\bsqlite3\.Error\b')),
  ('sqlite3.OperationalError', re.compile(r'\bsqlite3\.OperationalError\b')),
  ('sqlite3.IntegrityError', re.compile(r'\bsqlite3\.IntegrityError\b')),
  ('sqlite3.DatabaseError', re.compile(r'\bsqlite3\.DatabaseError\b')),
  ('PRAGMA', re.compile(r'\bPRAGMA\b')),
  ('last_insert_rowid', re.compile(r'\blast_insert_rowid\b')),
  ('sqlite_sequence', re.compile(r'\bsqlite_sequence\b')),
  ('INSERT OR REPLACE', re.compile(r'\bINSERT\s+OR\s+REPLACE\b', re.I)),
  ('INSERT OR IGNORE', re.compile(r'\bINSERT\s+OR\s+IGNORE\b', re.I)),
  ('? SQL placeholders', re.compile(r'\bVALUES\s*\([^)]*\?')),
  ('sqlite_master', re.compile(r'\bsqlite_master\b')),
]

ALLOWED_FALLBACK_BASEFILES = {
  'db_path.py',
  'system_audit.py',
}

# shared/db_connection.py and db_path.py are allowed only as explicit local fallback,
# but we still report hits and classify them as fallback-allowed if they are in those files.
ALLOWED_FALLBACK_BASEFILES.add('db_connection.py')


def is_excluded(path: str) -> bool:
  parts = path.split(os.sep)
  return any(p in EXCLUDE_DIRS for p in parts)


def classify(file_path: str) -> str:
  base = os.path.basename(file_path)
  # treat these as allowed fallback modules
  if base in {'db_path.py','shared_db_connection.py','db_connection.py','db_path.py'}:
    pass
  return 'unknown'


def classify_by_path(file_path: str) -> str:
  base = os.path.basename(file_path)
  if base in {'db_path.py','db_connection.py'}:
    return 'development/local fallback (allowed)'
  if 'tests' in file_path or '/tests/' in file_path.replace('\\','/') or base.startswith('test_'):
    return 'development/testing'
  return 'production (needs migration check)'


hits = []
per_file = defaultdict(list)

for path in glob.glob('**/*.py', recursive=True):
  if is_excluded(path):
    continue
  try:
    with open(path,'r',encoding='utf-8') as f:
      for i,line in enumerate(f,1):
        for name,pat in PATTERNS:
          if pat.search(line):
            # reduce placeholder noise a bit
            if name == '? SQL placeholders':
              u = line.upper()
              if not any(k in u for k in ['INSERT','SELECT','UPDATE','DELETE','VALUES','WHERE']):
                continue
            hits.append((path,i,name,line.strip()[:180]))
            per_file[path].append((i,name,line.strip()[:180]))
            break
  except Exception:
    continue

print('SQLITE_SYMBOL_SCAN')
print('Total hits:', len(hits))
print('Distinct files:', len(per_file))

for fp in sorted(per_file.keys()):
  cls = classify_by_path(fp)
  print(f'\nFILE {fp} [{cls}]')
  for i,name,snip in sorted(per_file[fp], key=lambda x:(x[0],x[1])):
    print(f'  L{i}: {name} | {snip}')

# compile check
print('\nPY_COMPILE')
compile_errors=[]
for path in glob.glob('**/*.py', recursive=True):
  if is_excluded(path):
    continue
  try:
    py_compile.compile(path, doraise=True)
  except Exception as e:
    compile_errors.append((path,str(e)))
print('Compile errors:', len(compile_errors))
for p,e in compile_errors:
  print(p,':',e)

