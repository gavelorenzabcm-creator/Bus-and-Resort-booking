import os,re,py_compile
from pathlib import Path
from collections import defaultdict

ROOT = Path('.')
EXCLUDE_DIRS = {'.venv','venv','__pycache__','build','dist','.git','.mypy_cache','node_modules','.pytest_cache','oracleJdk-26'}

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

ALLOWED_FALLBACK_BASEFILES = {'db_path.py','db_connection.py','system_audit.py'}

def is_excluded(p: Path) -> bool:
  return any(part in EXCLUDE_DIRS for part in p.parts)


def classify(fp: Path) -> str:
  if fp.name in ALLOWED_FALLBACK_BASEFILES:
    return 'development/local fallback (allowed)'
  if 'tests' in fp.parts or fp.name.startswith('test_'):
    return 'development/testing'
  return 'production (needs migration check)'


files = [p for p in ROOT.rglob('*.py') if not is_excluded(p)]

hits=[]
per_file=defaultdict(list)

for fp in files:
  try:
    txt = fp.read_text(encoding='utf-8', errors='ignore').splitlines()
  except Exception:
    continue
  for i,line in enumerate(txt,1):
    for name,pat in PATTERNS:
      if pat.search(line):
        if name == '? SQL placeholders':
          u=line.upper()
          if not any(k in u for k in ['INSERT','SELECT','UPDATE','DELETE','VALUES','WHERE']):
            continue
        per_file[str(fp)].append((i,name,line.strip()[:180]))
        hits.append((str(fp),i,name,line.strip()[:180]))
        break

print('SQLITE_SYMBOL_SCAN')
print('Total hits:', len(hits))
print('Distinct files:', len(per_file))
for fp in sorted(per_file.keys()):
  cls = classify(Path(fp))
  print(f'\nFILE {fp} [{cls}]')
  for i,name,snip in sorted(per_file[fp], key=lambda x:(x[0],x[1])):
    print(f'  L{i}: {name} | {snip}')

print('\nPY_COMPILE')
compile_errors=[]
for fp in files:
  try:
    py_compile.compile(str(fp), doraise=True)
  except Exception as e:
    compile_errors.append((str(fp),str(e)))
print('Compile errors:', len(compile_errors))
for p,e in compile_errors:
  print(p,':',e)

