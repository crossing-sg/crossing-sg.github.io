"""Persistent append-only numeric segment identities; no reuse of existing holes."""
import hashlib
import json
from pathlib import Path
import sqlite3


class Registry:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(self.path)
        self.db.executescript('''CREATE TABLE IF NOT EXISTS segments (
          uid TEXT PRIMARY KEY,seg_id INTEGER UNIQUE NOT NULL,geometry_sha256 TEXT NOT NULL,
          source TEXT NOT NULL,first_run TEXT NOT NULL,last_run TEXT NOT NULL,active INTEGER NOT NULL);
          CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY,value TEXT NOT NULL);''')
        self.db.commit()

    def allocate(self,existing,supplementary,run_id):
        """Each record has uid, geometry_sha256, source; existing also seg_id."""
        if len({r['uid'] for r in supplementary})!=len(supplementary):raise ValueError('Duplicate supplementary UID')
        if len({r['seg_id'] for r in existing})!=len(existing):raise ValueError('Duplicate existing seg_id')
        minimum=max(r['seg_id'] for r in existing)+1
        added=0
        try:
            self.db.execute('BEGIN IMMEDIATE')
            old=self.db.execute("SELECT value FROM metadata WHERE key='next_id'").fetchone()
            next_id=max(minimum,int(old[0]) if old else minimum)
            self.db.execute('UPDATE segments SET active=0')
            result={}
            for record in existing+sorted(supplementary,key=lambda r:r['uid']):
                prior=self.db.execute('SELECT seg_id,geometry_sha256,source FROM segments WHERE uid=?',(record['uid'],)).fetchone()
                if prior:
                    number,geometry_sha,source=prior
                    if geometry_sha!=record['geometry_sha256'] or source!=record['source']:
                        raise ValueError('Existing UID changed geometry/source: '+record['uid'])
                    if 'seg_id' in record and number!=record['seg_id']:raise ValueError('Existing ID was reassigned')
                    self.db.execute('UPDATE segments SET active=1,last_run=? WHERE uid=?',(run_id,record['uid']))
                else:
                    if 'seg_id' in record:number=int(record['seg_id'])
                    else:number=next_id;next_id+=1;added+=1
                    self.db.execute('INSERT INTO segments VALUES (?,?,?,?,?,?,1)',
                                    (record['uid'],number,record['geometry_sha256'],record['source'],run_id,run_id))
                result[record['uid']]=number
            self.db.execute("INSERT OR REPLACE INTO metadata VALUES ('next_id',?)",(str(next_id),))
            self.db.commit()
        except Exception:
            self.db.rollback();raise
        return result,added

    def export(self,path):
        rows=self.db.execute('SELECT uid,seg_id,geometry_sha256,source,first_run,last_run,active FROM segments ORDER BY seg_id').fetchall()
        names=['uid','seg_id','geometry_sha256','source','first_run','last_run','active']
        import csv
        with Path(path).open('w',encoding='utf-8',newline='') as f:
            writer=csv.writer(f);writer.writerow(names);writer.writerows(rows)
        return len(rows)

    def close(self):self.db.close()


def supplementary_uid(source,source_geometry_key,native_start_m,native_end_m,geometry_sha):
    text=f'{source}|{source_geometry_key}|{round(native_start_m*1000)}|{round(native_end_m*1000)}|{geometry_sha}'
    return 'proposal-v1-'+hashlib.sha256(text.encode()).hexdigest()[:32]
