from io import BytesIO
from urllib.parse import parse_qs,urlparse
import pytest
from src.backend.app import create_app
from src.backend.database import get_db
from src.backend.context_cache import ContextCache
from test_import_safety import workbook,budget,monthly,detail,db_dump


def client(tmp_path):
    return create_app({'TESTING':True,'DB_BASE_PATH':tmp_path,'DATA_BASE_PATH':tmp_path}).test_client()


def test_sync_route_combined_monthly_budget_and_read_path(tmp_path):
    c=client(tmp_path)
    result=c.post('/sync',data={'files':(BytesIO(workbook(budget(period=202501),monthly(),offset=3,right=2)),'arbitrary.xlsx'),'observed_months':'2025-01'})
    assert result.status_code==302
    assert 'sync_error' not in result.location
    facts=c.get('/history/monthly?year=2025&month=1').get_json()
    assert facts['facts']['A__0001']['quantity']==20
    assert facts['facts']['A__0001']['unit_price'] is None
    assert facts['daily_capabilities']['order_cycle'] is False


def test_sync_preview_no_writes_and_lists_coverage_decision(tmp_path):
    c=client(tmp_path);db=get_db(tmp_path);before=db_dump(db)
    result=c.post('/sync',data={'files':(BytesIO(workbook(monthly())),'a.xlsx'),'preview':'true'})
    assert result.status_code==200 and result.json['can_commit'] is False
    assert db_dump(db)==before


def test_cache_only_invalidated_after_successful_commit(tmp_path,monkeypatch):
    c=client(tmp_path);calls=[]
    monkeypatch.setattr(ContextCache,'invalidate_all',lambda self:calls.append('invalidate'))
    result=c.post('/sync',data={'files':(BytesIO(workbook(budget(value='broken'))),'a.xlsx')})
    assert 'sync_error' in result.location and calls==[]
    result=c.post('/sync',data={'files':(BytesIO(workbook(budget())),'b.xlsx')})
    assert 'sync_error' not in result.location and calls==['invalidate']


def shpb(qty=2):
    import pandas as pd
    return pd.DataFrame([{'出貨日期':20260101,'客戶代號':'C1','客戶簡稱':'A','產品':'0001','產品簡稱':'Synthetic',
                          '銷售數量':qty,'贈品數量':0,'銷貨淨價':3,'含稅淨額':qty*3,'折後業績':qty*3,
                          '發票編號':'I1','出貨單號':'S1','單別':'normal','業績屬性':'normal'}])


@pytest.mark.parametrize('route,field',[('/upload/current-month','file'),('/monitor/products/import','daily_sales_file')])
def test_daily_routes_shared_parser_and_closed_scope_guard(tmp_path,route,field):
    c=client(tmp_path);db=get_db(tmp_path)
    response=c.post(route,data={field:(BytesIO(workbook(shpb(),offset=5,right=2)),'renamed.xlsx')})
    assert 'error' not in response.location
    with db.get_connection() as conn:conn.execute('INSERT INTO month_close_records(year,month) VALUES (2026,1)')
    before=db_dump(db)
    response=c.post(route,data={field:(BytesIO(workbook(shpb(3))),'changed.xlsx'),'complete_months':'2026-01'})
    assert 'error' in response.location
    assert db_dump(db)==before


@pytest.mark.parametrize('route,field',[('/upload/current-month','file'),('/monitor/products/import','daily_sales_file')])
def test_daily_routes_fail_wrong_report_and_atomic_multifile_failure(tmp_path,route,field):
    c=client(tmp_path);db=get_db(tmp_path);before=db_dump(db)
    response=c.post(route,data={field:[(BytesIO(workbook(shpb())),'valid.xlsx'),(BytesIO(workbook(budget())),'wrong.xlsx')]})
    assert 'error' in response.location and db_dump(db)==before


def test_settings_exposes_package_and_explicit_scope_controls(tmp_path):
    c=client(tmp_path);response=c.get('/settings')
    text=response.get_data(as_text=True)
    assert 'name="files" accept=".xlsx" multiple' in text
    assert 'name="observed_months"' in text and 'name="complete_months"' in text


def test_monthly_only_upload_redirects_to_visible_analysis(tmp_path):
    c=client(tmp_path)
    response=c.post('/sync',data={'files':(BytesIO(workbook(monthly())),'history.xlsx'),'observed_months':'2025-01'})
    assert '/history/monthly/view?' in response.location
    page=c.get(response.location)
    assert page.status_code==200
    text=page.get_data(as_text=True)
    for value in ('A','0001','20.0','100.0','月彙總來源合計','日預測不可用'):
        assert value in text
    assert '這不代表實績為零' in c.get('/history/monthly/view?year=2025&month=2').get_data(as_text=True)


def test_customer_code_conflict_across_sync_route_is_atomic(tmp_path):
    c=client(tmp_path);db=get_db(tmp_path)
    first=budget();first['客戶代號']='C1'
    second=budget(value=99);second['客戶代號']='C2'
    for frame,ok in ((first,True),(second,False)):
        before=db_dump(db)
        response=c.post('/sync',data={'files':(BytesIO(workbook(frame)),'budget.xlsx')})
        assert ('sync_error' not in response.location)==ok
        if not ok:assert db_dump(db)==before
