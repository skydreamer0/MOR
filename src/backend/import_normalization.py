"""Typed fact adapters shared by all workbook entrypoints."""
from datetime import date
import numbers
import re
import pandas as pd
from src.backend.import_parser import (strict_date, strict_number, strict_identifier, strict_int,
                                      parse_period, is_blank, cell_label, BUDGET_LABELS, HISTORY_LABELS)

BUDGET_METRICS = {'02預算總量':('base_target_quantity','base_quantity'),
                  '04預算總額':('target_amount','source_defined_amount'),
                  '07預算S總量':('target_quantity','S_quantity')}
ACTUAL_METRICS = {'01銷+贈量':('base_quantity','base_quantity'),
                  '02銷+贈S量':('quantity','S_quantity'),
                  '03銷含稅總額':('taxed_amount','taxed_amount'),
                  '04銷未稅總額':('untaxed_amount','untaxed_amount'),
                  '05折後業績額':('bonus_amount','bonus_amount')}
# Exact ancillary budget-template labels, excluded by declared semantics only.
BUDGET_ANCILLARY = {'01銷+贈量','03銷售總額','05金達成率','06銷+贈S量'}


def product_identifier(value, label):
    from src.backend.data_loader import normalize_product_code
    text = strict_identifier(value, label)
    if normalize_product_code(text) != text:
        raise ValueError(f'{label}: ambiguous product text under legacy identity rules; provide the canonical product code')
    return text


def require_columns(frame, required):
    if not frame.columns.is_unique:
        raise ValueError('Duplicate semantic headers')
    missing = set(required) - set(frame.columns)
    if missing:
        raise ValueError('Missing columns: '+', '.join(sorted(missing)))
    if frame.empty:
        raise ValueError('No fact rows to import')


def monthly_facts(frame, kind, default_year=None, *, allow_duplicate_keys=False):
    require_columns(frame, {'客戶簡稱','商品號','標  題'})
    mapping = BUDGET_METRICS if kind == 'budget' else ACTUAL_METRICS
    # All numeric-looking headers are periods, including invalid ones: never silently skip 13/202613/1.5.
    month_columns = [c for c in frame.columns if isinstance(c,numbers.Real) or (isinstance(c,str) and re.match(r'^\s*[+\-]?(?:\d|\.\d)',c))]
    if not month_columns:
        raise ValueError('No month columns found in monthly sheet')
    facts, seen = [], set()
    for i, (_, row) in enumerate(frame.iterrows()):
        title=row['標  題']
        if title not in mapping:
            if kind == 'budget' and title in BUDGET_ANCILLARY:
                continue
            raise ValueError(f"{cell_label(frame,i,'標  題')}: unrecognized metric {title!r}")
        customer=strict_identifier(row['客戶簡稱'],cell_label(frame,i,'客戶簡稱'))
        product=product_identifier(row['商品號'],cell_label(frame,i,'商品號'))
        row_year=row.get('年')
        if '年' in frame and is_blank(row_year):
            raise ValueError(f"{cell_label(frame,i,'年')}: missing row year")
        periods=set()
        for header in month_columns:
            try:
                year,month=parse_period(header,row_year,default_year)
            except ValueError as exc:
                raise ValueError(f'{cell_label(frame,i,header)}: {exc}') from exc
            if (year,month) in periods:
                raise ValueError(f'{cell_label(frame,i,header)}: duplicate equivalent period')
            periods.add((year,month))
            metric,unit=mapping[title]
            key=(year,month,customer,product,metric)
            if key in seen and not allow_duplicate_keys:
                raise ValueError(f'{cell_label(frame,i,header)}: duplicate monthly business key')
            seen.add(key)
            facts.append({'year':year,'month':month,'customer_name':customer,'product_code':product,
                          'metric':metric,'unit':unit,'value':strict_number(row[header],cell_label(frame,i,header)),
                          'source_cell':cell_label(frame,i,header)})
    if not facts:
        raise ValueError('No recognized monthly facts')
    return pd.DataFrame(facts)


def budget_rows(frame, default_year=None):
    facts=monthly_facts(frame,'budget',default_year)
    rows=facts.pivot(index=['year','month','customer_name','product_code'],columns='metric',values='value').reset_index().rename_axis(None,axis=1)
    for metric,_ in BUDGET_METRICS.values():
        if metric not in rows:
            rows[metric]=None
    return rows[['year','month','customer_name','product_code','target_quantity','target_amount','base_target_quantity']]


def normalize_detail(frame, shpb=False):
    from src.backend.etl import SALES_COLUMNS, SHPB_COLUMNS
    mapping=SHPB_COLUMNS if shpb else SALES_COLUMNS
    require_columns(frame, mapping.values())
    result=[]
    for i,(_,r) in enumerate(frame.iterrows()):
        label=lambda key:cell_label(frame,i,mapping[key])
        if shpb and r[mapping['product_name']]=='每日總計' and all(is_blank(r[mapping[k]]) for k in ('order_date','customer_name','product_code')):
            continue
        if shpb:
            day=strict_date(r[mapping['order_date']],label('order_date'))
            qty=strict_number(r[mapping['sales_qty']],label('sales_qty'))+strict_number(r[mapping['gift_qty']],label('gift_qty'))
        else:
            try:
                day=date(*(strict_int(r[mapping[k]],label(k)) for k in ('year','month','day')))
            except ValueError as exc:
                raise ValueError(f'{label("day")}: invalid calendar date: {exc}') from exc
            qty=strict_number(r[mapping['quantity']],label('quantity'))
        result.append({'order_date':pd.Timestamp(day),
                       'customer_name':strict_identifier(r[mapping['customer_name']],label('customer_name')),
                       'product_code':product_identifier(r[mapping['product_code']],label('product_code')),
                       'product_name':'' if is_blank(r[mapping['product_name']]) else str(r[mapping['product_name']]),
                       'quantity':qty,'unit_price':strict_number(r[mapping['unit_price']],label('unit_price')),
                       'amount':strict_number(r[mapping['amount']],label('amount'))})
    if not result:
        raise ValueError('No daily facts to import')
    return pd.DataFrame(result)


def normalize_monitor(frame):
    from src.backend.daily_sales_importer import DAILY_SALES_COLUMNS as mapping
    require_columns(frame,mapping.values())
    result=[]
    for i,(_,r) in enumerate(frame.iterrows()):
        label=lambda key:cell_label(frame,i,mapping[key])
        if r[mapping['product_name']]=='每日總計' and all(is_blank(r[mapping[k]]) for k in ('sales_date','customer_name','product_code')):
            continue
        day=strict_date(r[mapping['sales_date']],label('sales_date'))
        record={'sales_year':day.year,'sales_month':day.month,'sales_date':day}
        for key in ('sales_quantity','gift_quantity','net_unit_price','taxed_amount','bonus_basis_amount'):
            record[key]=strict_number(r[mapping[key]],label(key))
        record['product_name']='' if is_blank(r[mapping['product_name']]) else str(r[mapping['product_name']])
        record['customer_name']=strict_identifier(r[mapping['customer_name']],label('customer_name'))
        record['product_code']=product_identifier(r[mapping['product_code']],label('product_code'))
        for key in ('customer_code','invoice_number','shipment_number','order_type','performance_type'):
            record[key]='' if is_blank(r[mapping[key]]) else strict_identifier(r[mapping[key]],label(key))
        record['actual_quantity']=record['sales_quantity']+record['gift_quantity']
        result.append(record)
    if not result:
        raise ValueError('每日業績檔沒有可匯入的明細列。')
    normalized=pd.DataFrame(result)
    if len(normalized[['sales_year','sales_month']].drop_duplicates()) != 1:
        raise ValueError('每日業績檔不可混用多個月份。')
    return normalized
