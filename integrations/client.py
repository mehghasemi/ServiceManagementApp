"""GET-only Dynamics adapter, inspired by MyBarid-AI's Windows transport.

No credential in command text, no CRM mutation endpoint, and no arbitrary URL fetch.
"""
import json
import os
import re
import subprocess
import time
from urllib.parse import urlsplit, urljoin, quote, unquote
from xml.etree import ElementTree as ET
from uuid import UUID

class CRMError(Exception):
    pass

class Cancelled(CRMError):
    pass

def validate_connection(base, organization, version):
    parsed = urlsplit(base)
    permitted = {host.strip().lower() for host in os.environ.get('SERVICE_CRM_ALLOWED_HOSTS', 'crm.baridsoft.ir').split(',')}
    if parsed.scheme != 'https' or parsed.hostname not in permitted or parsed.port not in (None, 443) or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('', '/'):
        raise CRMError('آدرس باید HTTPS و میزبان CRM مجاز باشد؛ فهرست میزبان‌های مجاز فقط در محیط سرور تنظیم می‌شود.')
    if not re.fullmatch(r'[A-Za-z0-9_-]+', organization) or not re.fullmatch(r'v\d+\.\d+', version):
        raise CRMError('نام سازمان یا نسخه API معتبر نیست.')

class Client:
    def __init__(self, config, checkpoint=None):
        validate_connection(config['base_url'], config['organization'], config['api_version'])
        self.root = f"{config['base_url'].rstrip('/')}/{config['organization']}/api/data/{config['api_version']}"
        self.timeout = int(config.get('request_timeout', 60))
        self.checkpoint = checkpoint or (lambda *args: None)
        self.started = time.monotonic()

    def get(self, path):
        self.checkpoint('ارتباط فقط‌خواندنی با CRM', 0)
        if time.monotonic() - self.started > 900:
            raise CRMError('مهلت کل دریافت تمام شد؛ داده قبلی حفظ شده است.')
        url = path if path.startswith('https://') else f'{self.root}/{path}'
        parsed = urlsplit(url)
        root = urlsplit(self.root)
        if (parsed.scheme, parsed.netloc) != (root.scheme, root.netloc) or not unquote(parsed.path).startswith(root.path + '/') or '..' in unquote(parsed.path) or parsed.fragment:
            raise CRMError('مسیر صفحه بعد خارج از CRM مجاز است؛ دریافت متوقف شد.')
        command = '''$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false)
try {
 $headers=@{Accept='application/json';'OData-Version'='4.0';Prefer='odata.include-annotations="*"'}
 $r=Invoke-WebRequest -UseBasicParsing -Uri $env:SERVICE_REQUEST_URL -UseDefaultCredentials -Method Get -MaximumRedirection 0 -Headers $headers -TimeoutSec ([int]$env:SERVICE_REQUEST_TIMEOUT)
 [Console]::Write([System.Text.Encoding]::UTF8.GetString($r.RawContentStream.ToArray()))
} catch { $status=0; if ($_.Exception.Response) {$status=[int]$_.Exception.Response.StatusCode}; [Console]::Write('{"transport_error":'+$status+'}'); exit 22 }
'''
        env = os.environ.copy()
        env.update(SERVICE_REQUEST_URL=url, SERVICE_REQUEST_TIMEOUT=str(self.timeout))
        try:
            result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', command], capture_output=True, text=True, encoding='utf-8-sig', errors='replace', timeout=self.timeout + 10, env=env, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except subprocess.TimeoutExpired as error:
            raise CRMError('مهلت پاسخ CRM تمام شد؛ اتصال شبکه را بررسی و دریافت را دوباره اجرا کنید.') from error
        except OSError as error:
            raise CRMError('ابزار اتصال ویندوز در دسترس نیست؛ این اتصال فعلاً به PowerShell ویندوز نیاز دارد.') from error
        self.checkpoint('پاسخ CRM دریافت شد', 0)
        try:
            payload = json.loads(result.stdout)
        except ValueError as error:
            raise CRMError('پاسخ CRM قابل خواندن نیست؛ آدرس سازمان و مجوز را بررسی کنید.') from error
        if result.returncode or 'transport_error' in payload:
            raise CRMError(f"ارتباط CRM ناموفق بود (HTTP {payload.get('transport_error', 0)}). دسترسی ویندوز و شبکه را بررسی کنید؛ داده قبلی حفظ شد.")
        return payload

    def paged(self, path):
        rows, seen = [], set()
        for _ in range(200):
            if path in seen:
                raise CRMError('صفحه‌بندی تکراری است؛ دریافت ناقص پذیرفته نشد.')
            seen.add(path)
            payload = self.get(path)
            if not isinstance(payload.get('value'), list):
                raise CRMError('پاسخ فهرست CRM معتبر نیست.')
            rows.extend(payload['value'])
            path = payload.get('@odata.nextLink')
            if not path:
                return rows
        raise CRMError('حد ایمنی صفحه‌بندی پر شد؛ داده قبلی حفظ شد.')

    def catalog(self):
        rows = []
        for kind, key in [('userqueries', 'userqueryid'), ('savedqueries', 'savedqueryid')]:
            for row in self.paged(f'{kind}?$select=name,{key},returnedtypecode'):
                entity = str(row.get('returnedtypecode', ''))
                entity = {'112': 'incident', '5': 'annotation', '4200': 'activitypointer', '4212': 'task'}.get(entity, entity)
                if entity in ('incident', 'annotation', 'task', 'activitypointer', 'brd_project'):
                    rows.append({'kind': kind, 'crm_id': str(UUID(row[key])), 'name': row.get('name', ''), 'entity': entity})
        return rows

    def fetch_view(self, view, related_ids=None):
        kind, identifier = view['kind'], str(UUID(view['crm_id']))
        if kind not in ('userqueries', 'savedqueries'):
            raise CRMError('نوع View معتبر نیست.')
        definition = self.get(f'{kind}({identifier})?$select=name,fetchxml,returnedtypecode')
        xml = definition.get('fetchxml') or ''
        if '<!DOCTYPE' in xml.upper() or '<!ENTITY' in xml.upper():
            raise CRMError('ساختار View پشتیبانی نمی‌شود.')
        try:
            root = ET.fromstring(xml)
        except ET.ParseError as error:
            raise CRMError('ساختار View قابل خواندن نیست.') from error
        entity = root.find('entity')
        sets = {'incident': 'incidents', 'annotation': 'annotations', 'task': 'tasks', 'activitypointer': 'activitypointers', 'brd_project': 'brd_projects'}
        if entity is None or entity.get('name') != view['entity'] or view['entity'] not in sets or root.get('aggregate') == 'true':
            raise CRMError('View انتخاب‌شده باید فهرست رکوردهای غیرتجمیعی همان موجودیت باشد.')
        # Retain the complete View filters/joins. Add only available columns, never rows.
        names = self.paged(f"EntityDefinitions(LogicalName='{view['entity']}')/Attributes?$select=LogicalName")
        available = {row['LogicalName'] for row in names}
        needed = {
            'brd_project': ('brd_projectid', 'brd_name', 'statuscode', 'statecode', 'brd_account', 'brd_customer', 'brd_projectmanager', 'brd_plannedenddate', 'brd_realenddate', 'brd_lastnotedate', 'brd_lastaction', 'brd_currentphase', 'brd_progress', 'modifiedon'),
            'incident': ('incidentid', 'ticketnumber', 'title', 'createdon', 'modifiedon', 'statuscode', 'statecode', 'customerid', 'brd_account', 'brd_plannedcase', 'ownerid', 'brd_startplanningdate'),
            'annotation': ('annotationid', 'objectid', 'subject', 'notetext', 'modifiedon', 'createdon'),
            'task': ('activityid', 'regardingobjectid', 'subject', 'description', 'scheduledend', 'statecode', 'modifiedon'),
            'activitypointer': ('activityid', 'regardingobjectid', 'subject', 'description', 'scheduledend', 'statecode', 'modifiedon'),
        }[view['entity']]
        selected = {a.get('name') for a in entity.findall('attribute')}
        if entity.find('all-attributes') is None:
            for name in needed:
                if name in available and name not in selected:
                    ET.SubElement(entity, 'attribute', {'name': name})
        if related_ids is not None:
            if view['entity'] != 'annotation':
                raise CRMError('محدودسازی ارتباط فقط برای View یادداشت مجاز است.')
            if not related_ids:
                return [], xml, definition.get('name', '')
            condition = ET.SubElement(ET.SubElement(entity, 'filter', {'type': 'and'}), 'condition', {'attribute': 'objectid', 'operator': 'in'})
            for identifier in sorted(set(related_ids)):
                ET.SubElement(condition, 'value').text = str(UUID(identifier))
        original_top = root.get('top')
        if original_top:
            root.attrib.pop('count', None)
            root.attrib.pop('page', None)
        else:
            root.set('count', '500')
            root.set('page', '1')
        root.attrib.pop('paging-cookie', None)
        all_rows, seen_pages = [], set()
        next_link = None
        for page in range(1, 201):
            payload = self.get(next_link or f"{sets[view['entity']]}?fetchXml={quote(ET.tostring(root, encoding='unicode'), safe='')}")
            rows = payload.get('value')
            if not isinstance(rows, list):
                raise CRMError('داده View معتبر نیست.')
            signature = json.dumps(rows, sort_keys=True)
            if rows and signature in seen_pages:
                raise CRMError('صفحه تکراری دریافت شد؛ ذخیره ناقص لغو شد.')
            seen_pages.add(signature)
            all_rows.extend(rows)
            self.checkpoint(f"دریافت View {definition.get('name', '')}", len(all_rows))
            next_link = payload.get('@odata.nextLink')
            if next_link:
                continue
            cookie = payload.get('@Microsoft.Dynamics.CRM.fetchxmlpagingcookie')
            more = payload.get('@Microsoft.Dynamics.CRM.morerecords')
            if more in (False, 'false') or (not cookie and more not in (True, 'true') and len(rows) < 500) or (original_top and len(all_rows) >= int(original_top)):
                return all_rows, xml, definition.get('name', view['name'])
            root.set('page', str(page + 1))
            if cookie:
                wrapper = ET.fromstring(cookie)
                raw_cookie = wrapper.get('pagingcookie')
                root.set('paging-cookie', unquote(unquote(raw_cookie)) if raw_cookie else cookie)
        raise CRMError('حد صفحات View پر شد؛ دریافت ناقص ذخیره نشد.')
