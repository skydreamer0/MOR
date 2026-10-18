"""Monthly history repository: metrics never masquerade as daily transactions."""
from src.backend.row_identity import make_row_id


def fetch_monthly_actuals(db,year,month):
    with db.get_connection() as conn:
        rows=conn.execute('SELECT customer_name,product_code,metric,value FROM monthly_actual_facts WHERE year=? AND month=?',(year,month)).fetchall()
    result={}
    for row in rows:
        key=make_row_id(row['customer_name'],row['product_code'])
        entry=result.setdefault(key,{'customer_name':row['customer_name'],'product_code':row['product_code'],
                                    'granularity':'month','latest_order_day':None,'unit_price':None,'order_cycle':None})
        entry[row['metric']]=float(row['value'])
    return result


def add_monthly_quantity_history(db,year,month,daily):
    result=dict(daily)
    for key,row in fetch_monthly_actuals(db,year,month).items():
        if key in result:
            raise ValueError('Monthly and daily history overlap; reconcile imported sources')
        if 'quantity' in row:
            result[key]=row['quantity']
    return result
