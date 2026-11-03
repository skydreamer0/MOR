"""Whole-package preflight and atomic SQLite persistence.

Default writes are non-destructive. Daily replacements need explicit complete
month coverage; a row's presence is never evidence of a complete month.
"""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import pandas as pd

from src.backend.import_parser import ParsedTable, parse_workbook, parse_period
from src.backend.import_normalization import monthly_facts, normalize_detail, normalize_monitor

DETAIL_COLUMNS = ['order_date','customer_name','product_code','product_name','quantity','unit_price','amount']
MONITOR_COLUMNS = ['sales_year','sales_month','sales_date','customer_code','customer_name','product_code','product_name',
                   'sales_quantity','gift_quantity','actual_quantity','net_unit_price','taxed_amount','bonus_basis_amount',
                   'invoice_number','shipment_number','order_type','performance_type']
BUDGET_METRIC_COLUMNS = {'target_quantity','target_amount','base_target_quantity'}


def scalar(value):
    if value is None or pd.isna(value):
        return None
    if isinstance(value,(date,datetime,pd.Timestamp)):
        return value.strftime('%Y-%m-%d')
    return value.item() if hasattr(value,'item') else value


def _tuples(frame,columns):
    return [tuple(scalar(v) for v in row) for row in frame[columns].itertuples(index=False,name=None)]


def _json(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))


def parse_period_selection(value):
    """Explicit HTML/API selection: comma-separated YYYY-MM. Never inferred."""
    if not value:
        return set()
    result=set()
    for item in value.split(','):
        try:
            year,month=item.strip().split('-')
            if len(year)!=4 or len(month)!=2:
                raise ValueError()
            result.add(parse_period(year+month))
        except ValueError:
            raise ValueError('Periods must be comma-separated YYYY-MM') from None
    return result


@dataclass
class ImportPlan:
    intent: str
    frames: dict[str,pd.DataFrame]
    manifest: list[dict]
    package_hash: str
    complete_months: set[tuple[int,int]]=field(default_factory=set)
    observed_months: set[tuple[int,int]]=field(default_factory=set)
    duplicate_artifacts: int=0
    unresolved: list[str]=field(default_factory=list)
    customer_bindings: dict[str,str]=field(default_factory=dict)

    def preview(self):
        return {'intent':self.intent,'package_hash':self.package_hash,
                'tables':self.manifest,'counts':{k:len(v) for k,v in self.frames.items()},
                'complete_months':sorted(self.complete_months),'observed_months':sorted(self.observed_months),
                'duplicate_artifacts_skipped':self.duplicate_artifacts,
                'unresolved':self.unresolved,'can_commit':not self.unresolved,
                'daily_replacement':'only explicitly declared complete months',
                'monthly_replacement':'supplied metric keys only; absent metrics preserved',
                'monthly_daily_capabilities':{'order_cycles':False,'latest_order_day':False,'unit_price':False}}


def preflight(files, *, intent='sync', default_budget_year=None, complete_months=None,
              observed_months=None, daily_partitions=False, deduplicate_monthly=False, allow_unresolved=False):
    if intent not in {'sync','current','monitor'}:
        raise ValueError('Unknown import operation intent')
    if not files or len(files)>50:
        raise ValueError('Select between 1 and 50 workbooks')
    if sum(len(payload) for _,payload in files)>100*1024*1024:
        raise ValueError('Selected package exceeds 100 MiB')
    tables=[]; hashes=set(); duplicate_artifacts=0
    for filename,payload in files:
        digest=hashlib.sha256(payload).hexdigest()
        if digest in hashes:
            duplicate_artifacts+=1
            continue
        hashes.add(digest)
        tables.extend(parse_workbook(payload,filename))
    return plan_tables(tables,intent=intent,default_budget_year=default_budget_year,
                       complete_months=complete_months,observed_months=observed_months,
                       daily_partitions=daily_partitions,deduplicate_monthly=deduplicate_monthly,
                       duplicate_artifacts=duplicate_artifacts, allow_unresolved=allow_unresolved)


def plan_tables(tables, *, intent='sync', default_budget_year=None, complete_months=None,
                observed_months=None, daily_partitions=False, deduplicate_monthly=False,
                duplicate_artifacts=0, allow_unresolved=False):
    complete_months=set(complete_months or ());observed_months=set(observed_months or ())
    for y,m in complete_months|observed_months:
        parse_period(m,y)
    frames={};manifest=[];daily_scopes={};monthly_keys={};all_monthly_periods=set();unresolved=[]
    name_to_code={}
    for table in tables:
        if '客戶代號' in table.frame and '客戶簡稱' in table.frame:
            from src.backend.import_parser import is_blank, strict_identifier
            for _,identity in table.frame[['客戶代號','客戶簡稱']].iterrows():
                if is_blank(identity['客戶代號']):continue
                code=strict_identifier(identity['客戶代號'],'customer code')
                name=strict_identifier(identity['客戶簡稱'],'customer name')
                if name in name_to_code and name_to_code[name]!=code:
                    raise ValueError('Conflicting customer code/name mapping; existing name-based identity cannot safely merge these facts')
                name_to_code[name]=code
        kind=table.kind
        if intent in {'current','monitor'} and kind!='shpb':
            raise ValueError(f'{intent}: expected SHPB daily detail, received {kind}')
        if intent=='sync' and kind=='shpb':
            raise ValueError('SHPB detail needs an explicit current-month or monitor operation')
        if kind in {'budget','monthly_actual'}:
            rows=monthly_facts(table.frame,kind,default_budget_year if kind=='budget' else None, allow_duplicate_keys=True)
            if kind=='monthly_actual':
                periods=set(zip(rows.year,rows.month));all_monthly_periods |= periods
                if not observed_months:
                    message='Monthly actuals require observed_months selection; zero template cells do not prove observed months'
                    if not allow_unresolved:raise ValueError(message)
                    if message not in unresolved:unresolved.append(message)
                else:
                    rows=rows[[p in observed_months for p in zip(rows.year,rows.month)]].copy()
                if rows.empty:
                    raise ValueError('Observed-month selection includes no facts from a monthly table')
            keep=[]
            for index,r in rows.iterrows():
                key=(kind,int(r.year),int(r.month),r.customer_name,r.product_code,r.metric)
                value=(r.unit,float(r.value))
                if key in monthly_keys:
                    if not deduplicate_monthly or monthly_keys[key]!=value:
                        raise ValueError(f'Overlapping monthly fact {key}; select source or explicit equal-fact deduplication')
                    continue
                monthly_keys[key]=value;keep.append(index)
            rows=rows.loc[keep]
        else:
            kind='monitor' if intent=='monitor' else ('current' if intent=='current' else 'sales')
            rows=normalize_monitor(table.frame) if kind=='monitor' else normalize_detail(table.frame,shpb=kind=='current')
            scopes=_daily_scopes(rows,kind)
            overlap=set(scopes)&set(daily_scopes)
            if overlap and not daily_partitions:
                raise ValueError('Overlapping daily tables without stable line identity; explicitly declare disjoint partitions or select one source')
            for scope in scopes:
                daily_scopes[scope]=kind
        source=table.source()
        if kind in {'budget','monthly_actual'}:
            source['metrics']=rows[['metric','unit']].drop_duplicates().to_dict('records')
        source['source_row_count']=len(table.frame)
        source.update({'kind':kind,'accepted_rows':len(rows),'rejected_rows':0,
                       'periods':sorted(_periods(rows,kind))})
        # Source cells survive monthly pivoting; daily provenance retains each input row coordinate.
        source['source_columns']={str(k):v for k,v in table.frame.attrs.get('columns',{}).items()}
        source['source_rows']=table.frame.attrs.get('rows',list(range(2,len(table.frame)+2)))
        manifest.append(source)
        frames.setdefault(kind,[]).append(rows)
    frames={kind:pd.concat(parts,ignore_index=True) for kind,parts in frames.items()}
    if not frames or not any(len(r) for r in frames.values()):
        raise ValueError('No recognized facts in package')
    if observed_months-all_monthly_periods and 'monthly_actual' in frames:
        raise ValueError('Observed-month selection contains periods absent from monthly input')
    if 'monthly_actual' in frames:
        from src.backend.import_normalization import ACTUAL_METRICS
        expected={metric for metric,_ in ACTUAL_METRICS.values()}
        for key,group in frames['monthly_actual'].groupby(['year','month','customer_name','product_code']):
            missing=expected-set(group.metric)
            if missing:
                raise ValueError(f'Monthly actual scope {key} lacks required metrics: {sorted(missing)}')
    if 'monitor' in frames and len(_periods(frames['monitor'],'monitor'))!=1:
        raise ValueError('每日業績檔不可混用多個月份。')
    daily_periods=set().union(*(_periods(r,k) for k,r in frames.items() if k in {'sales','current','monitor'}))
    if complete_months-daily_periods:
        raise ValueError('Complete-month selection contains months absent from daily input')
    if 'monthly_actual' in frames:
        monthly_scopes={(int(r.year),int(r.month),r.customer_name,r.product_code) for r in frames['monthly_actual'].itertuples()}
        if monthly_scopes & set(daily_scopes):
            raise ValueError('Monthly summaries and daily detail overlap; select one granularity for each scope')
    canonical={k:sorted((_json([scalar(v) for v in row]) for row in r.drop(columns=['source_cell'],errors='ignore').itertuples(index=False,name=None))) for k,r in frames.items()}
    digest=hashlib.sha256(_json({'intent':intent,'facts':canonical,'customer_bindings':name_to_code,'complete':sorted(complete_months),'observed':sorted(observed_months)}).encode()).hexdigest()
    return ImportPlan(intent,frames,manifest,digest,complete_months,observed_months,duplicate_artifacts,unresolved,name_to_code)


def _periods(frame,kind):
    if frame.empty:return set()
    if kind in {'budget','monthly_actual'}:return {(int(y),int(m)) for y,m in zip(frame.year,frame.month)}
    if kind=='monitor':return {(int(y),int(m)) for y,m in zip(frame.sales_year,frame.sales_month)}
    return {(v.year,v.month) for v in frame.order_date}


def _daily_scopes(frame,kind):
    dates=frame.sales_date if kind=='monitor' else frame.order_date
    return {(d.year,d.month,c,p) for d,c,p in zip(dates,frame.customer_name,frame.product_code)}


def _check_closed(conn,periods):
    for year,month in periods:
        if conn.execute('SELECT 1 FROM month_close_records WHERE year=? AND month=?',(year,month)).fetchone():
            raise ValueError(f'{year}/{month:02d} 已結月，不可覆蓋。如需修改請先解除結月。')


def insert_frame(conn,table,frame,columns):
    allowed={'sales_records':DETAIL_COLUMNS,'current_month_records':DETAIL_COLUMNS,
             'daily_sales_actuals':MONITOR_COLUMNS+['import_batch_id']}
    if table not in allowed or columns!=allowed[table]:
        raise ValueError('Unapproved SQL insert shape')
    conn.executemany(f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",_tuples(frame,columns))


def commit_plan(db,plan):
    if plan.unresolved:
        raise ValueError('; '.join(plan.unresolved))
    result={'counts':{k:len(v) for k,v in plan.frames.items()},'changed':False,'batch_id':None,'preview':plan.preview()}
    with db.get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        periods=set().union(*(_periods(r,k) for k,r in plan.frames.items()))
        _check_closed(conn,periods)
        _validate_customer_bindings(conn,plan)
        # Validate every DB overlap before any delete/insert.
        for kind,frame in plan.frames.items():
            if kind in {'sales','current','monitor'}:
                _validate_daily_overlap(conn,kind,frame,plan.complete_months)
            elif kind=='monthly_actual':
                _validate_monthly_overlap(conn,frame)
        changed=[]
        for kind,frame in plan.frames.items():
            if kind=='budget':
                changed.extend(_write_budget(conn,frame))
            elif kind=='monthly_actual':
                changed.extend(_write_monthly(conn,frame))
            else:
                batch_id,keys=_write_daily(conn,kind,frame,plan)
                result['batch_id']=batch_id or result['batch_id'];changed.extend(keys)
        for name,code in plan.customer_bindings.items():
            conn.execute('INSERT INTO import_customer_bindings(customer_name,customer_code) VALUES (?,?) ON CONFLICT DO NOTHING',(name,code))
        if changed:
            cursor=conn.execute('INSERT INTO import_receipts (package_hash,intent,manifest) VALUES (?,?,?)',
                                (plan.package_hash,plan.intent,_json(plan.manifest)))
            receipt_id=cursor.lastrowid
            conn.executemany('INSERT INTO import_fact_sources (kind,fact_key,receipt_id,sources) VALUES (?,?,?,?) '
                             'ON CONFLICT(kind,fact_key) DO UPDATE SET receipt_id=excluded.receipt_id,sources=excluded.sources',
                             [(kind,_json(key),receipt_id,_source_for_key(plan,kind,key)) for kind,key in changed])
            result['changed']=True
            result['receipt_id']=receipt_id
    return result


def _validate_monthly_overlap(conn,frame):
    scopes={(int(r.year),int(r.month),r.customer_name,r.product_code) for r in frame.itertuples()}
    for y,m,c,p in scopes:
        for table,datecol in [('sales_records','order_date'),('current_month_records','order_date'),('daily_sales_actuals','sales_date')]:
            if conn.execute(f'SELECT 1 FROM {table} WHERE substr({datecol},1,7)=? AND customer_name=? AND product_code=? LIMIT 1',(f'{y:04d}-{m:02d}',c,p)).fetchone():
                raise ValueError(f'Monthly/daily overlap for {y}-{m:02d}, {c}, {p}; select a source before import')


def _validate_daily_overlap(conn,kind,frame,complete_months):
    target={'sales':'sales_records','current':'current_month_records','monitor':'daily_sales_actuals'}[kind]
    for y,m,c,p in _daily_scopes(frame,kind):
        if conn.execute('SELECT 1 FROM monthly_actual_facts WHERE year=? AND month=? AND customer_name=? AND product_code=? LIMIT 1',(y,m,c,p)).fetchone():
            raise ValueError('Daily detail overlaps monthly summary; explicit source reconciliation required')
        other='current_month_records' if kind=='sales' else 'sales_records'
        if kind!='monitor' and conn.execute(f'SELECT 1 FROM {other} WHERE substr(order_date,1,7)=? AND customer_name=? AND product_code=? LIMIT 1',(f'{y:04d}-{m:02d}',c,p)).fetchone():
            # Historical promotion only with explicitly complete month, retired atomically below.
            if kind!='sales' or (y,m) not in complete_months:
                raise ValueError('Historical/current detail overlap; declare a complete historical replacement or select one source')
    for y,m in _periods(frame,kind):
        columns=MONITOR_COLUMNS if kind=='monitor' else DETAIL_COLUMNS
        datecol='sales_date' if kind=='monitor' else 'order_date'
        existing=conn.execute(f"SELECT {','.join(columns)} FROM {target} WHERE substr({datecol},1,7)=?",(f'{y:04d}-{m:02d}',)).fetchall()
        incoming=_month_frame(frame,kind,y,m)
        incoming_scopes=set(zip(incoming.customer_name,incoming.product_code))
        compared=[r for r in existing if (r['customer_name'],r['product_code']) in incoming_scopes]
        if compared and Counter(tuple(row) for row in compared)!=Counter(_tuples(incoming,columns)) and (y,m) not in complete_months:
            for c,p in incoming_scopes:
                previous=[tuple(r) for r in compared if (r['customer_name'],r['product_code'])==(c,p)]
                current=incoming[(incoming.customer_name==c)&(incoming.product_code==p)]
                if previous and Counter(previous)!=Counter(_tuples(current,columns)):
                    raise ValueError(f'{y}-{m:02d}: overlapping daily snapshot requires explicit complete_months coverage')



def _month_frame(frame,kind,y,m):
    dates=frame.sales_date if kind=='monitor' else frame.order_date
    return frame[[(d.year,d.month)==(y,m) for d in dates]]


def _write_daily(conn,kind,frame,plan):
    target={'sales':'sales_records','current':'current_month_records','monitor':'daily_sales_actuals'}[kind]
    columns=MONITOR_COLUMNS if kind=='monitor' else DETAIL_COLUMNS
    datecol='sales_date' if kind=='monitor' else 'order_date'
    batch_id=None;changes=[]
    for y,m in sorted(_periods(frame,kind)):
        incoming=_month_frame(frame,kind,y,m)
        existing=conn.execute(f"SELECT {','.join(columns)} FROM {target} WHERE substr({datecol},1,7)=?",(f'{y:04d}-{m:02d}',)).fetchall()
        if (y,m) not in plan.complete_months:
            existing_scopes={(r['customer_name'],r['product_code']) for r in existing}
            # Validation proved overlapping scopes are identical multisets, including duplicate rows.
            incoming=incoming[[pair not in existing_scopes for pair in zip(incoming.customer_name,incoming.product_code)]]
            identical=incoming.empty
        else:
            identical=Counter(tuple(r) for r in existing)==Counter(_tuples(incoming,columns))
        if identical:
            if kind=='monitor':
                row=conn.execute('SELECT import_batch_id FROM daily_sales_actuals WHERE sales_year=? AND sales_month=? LIMIT 1',(y,m)).fetchone()
                batch_id=row[0] if row else None
        else:
            if (y,m) in plan.complete_months:
                _retire_daily_sources(conn,kind,y,m)
                conn.execute(f'DELETE FROM {target} WHERE substr({datecol},1,7)=?',(f'{y:04d}-{m:02d}',))
            if kind=='monitor':
                cursor=conn.execute('INSERT INTO daily_import_batches (source_filename,source_hash,sales_year,sales_month,row_count,date_start,date_end,quantity_total,taxed_amount_total,status,message) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                                    ('; '.join(x['filename'] for x in plan.manifest),plan.package_hash,y,m,len(incoming),str(incoming.sales_date.min()),str(incoming.sales_date.max()),float(incoming.actual_quantity.sum()),float(incoming.taxed_amount.sum()),'success','匯入完成'))
                batch_id=cursor.lastrowid
                incoming=incoming.assign(import_batch_id=batch_id)
                insert_frame(conn,target,incoming,MONITOR_COLUMNS+['import_batch_id'])
            else:
                insert_frame(conn,target,incoming,DETAIL_COLUMNS)
            changes.extend((kind,(y,m,c,p)) for c,p in set(zip(incoming.customer_name,incoming.product_code)))
        if kind=='sales' and (y,m) in plan.complete_months:
            retired=conn.execute('DELETE FROM current_month_records WHERE substr(order_date,1,7)=?',(f'{y:04d}-{m:02d}',)).rowcount
            if retired:_retire_daily_sources(conn,'current',y,m)
            if retired:changes.append(('current_retired',(y,m)))
    return batch_id,changes


def _write_budget(conn,frame):
    changed=[]
    for r in frame.itertuples():
        key=(int(r.year),int(r.month),r.customer_name,r.product_code)
        if r.metric not in BUDGET_METRIC_COLUMNS:raise ValueError('Unknown budget metric')
        old=conn.execute(f'SELECT {r.metric} FROM budget_targets WHERE year=? AND month=? AND customer_name=? AND product_code=?',key).fetchone()
        if old is not None and old[0]==r.value:continue
        # Missing metrics are NULL, never manufactured zeros. Existing other metrics remain unchanged.
        conn.execute('INSERT INTO budget_targets (year,month,customer_name,product_code,target_quantity,target_amount,base_target_quantity) VALUES (?,?,?,?,NULL,NULL,NULL) ON CONFLICT DO NOTHING',key)
        conn.execute(f'UPDATE budget_targets SET {r.metric}=? WHERE year=? AND month=? AND customer_name=? AND product_code=?',(float(r.value),)+key)
        changed.append(('budget',key+(r.metric,)))
    return changed


def _write_monthly(conn,frame):
    changed=[]
    for r in frame.itertuples():
        key=(int(r.year),int(r.month),r.customer_name,r.product_code,r.metric)
        old=conn.execute('SELECT unit,value FROM monthly_actual_facts WHERE year=? AND month=? AND customer_name=? AND product_code=? AND metric=?',key).fetchone()
        if old is not None and tuple(old)==(r.unit,r.value):continue
        conn.execute('INSERT INTO monthly_actual_facts (year,month,customer_name,product_code,metric,unit,value) VALUES (?,?,?,?,?,?,?) ON CONFLICT(year,month,customer_name,product_code,metric) DO UPDATE SET unit=excluded.unit,value=excluded.value',key+(r.unit,float(r.value)))
        changed.append(('monthly_actual',key))
    return changed


def _source_for_key(plan,kind,key):
    if kind in {'budget','monthly_actual'}:
        rows=plan.frames[kind]
        matched=rows[(rows.year==key[0]) & (rows.month==key[1]) & (rows.customer_name==key[2]) & (rows.product_code==key[3]) & (rows.metric==key[4])]
        return _json({'cells':matched.source_cell.tolist()})
    return _json({'scope':key,'location':'receipt manifest source rows'})


def preview_plan(db,plan):
    result=plan.preview()
    conflicts=list(plan.unresolved)
    with db.get_connection() as conn:
        try:
            _validate_customer_bindings(conn,plan)
            _check_closed(conn,set().union(*(_periods(r,k) for k,r in plan.frames.items())))
            for kind,frame in plan.frames.items():
                if kind in {'sales','current','monitor'}:
                    _validate_daily_overlap(conn,kind,frame,plan.complete_months)
                elif kind=='monthly_actual':
                    _validate_monthly_overlap(conn,frame)
        except ValueError as exc:
            conflicts.append(str(exc))
    result['unresolved']=conflicts
    result['can_commit']=not conflicts
    result['note']='Commit rechecks locks and overlaps inside its transaction.'
    return result


def _retire_daily_sources(conn,kind,year,month):
    # Scoped JSON keys retain separate receipt associations for disjoint appends.
    for row in conn.execute('SELECT fact_key FROM import_fact_sources WHERE kind=?',(kind,)).fetchall():
        if json.loads(row['fact_key'])[:2]==[year,month]:
            conn.execute('DELETE FROM import_fact_sources WHERE kind=? AND fact_key=?',(kind,row['fact_key']))


def _validate_customer_bindings(conn,plan):
    for name,code in plan.customer_bindings.items():
        known={r[0] for r in conn.execute('SELECT customer_code FROM import_customer_bindings WHERE customer_name=?',(name,))}
        known.update(r[0] for r in conn.execute("SELECT DISTINCT customer_code FROM daily_sales_actuals WHERE customer_name=? AND customer_code IS NOT NULL AND customer_code<>''",(name,)))
        if known and known!={code}:
            raise ValueError('Conflicting persisted customer identity mapping; resolve customer codes before import')
        if not known:
            for table in ('budget_targets','monthly_actual_facts','sales_records','current_month_records'):
                if conn.execute(f'SELECT 1 FROM {table} WHERE customer_name=? LIMIT 1',(name,)).fetchone():
                    raise ValueError('Legacy customer identity mapping is unverified; resolve existing name/code binding before import')
