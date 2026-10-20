"""Evidence-led normalization; no semantic inference from titles or absent notes."""
from xml.etree import ElementTree as ET
from uuid import UUID

FORMAT = '@OData.Community.Display.V1.FormattedValue'

def guid(value):
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        return ''

def label(row, name):
    return str(row.get(name + FORMAT) or row.get(name) or '')

def normalize(rows, xml, notes=None, activities=None):
    entity = ET.fromstring(xml).find('entity')
    parent_aliases = [link.get('alias') for link in entity.findall('link-entity') if link.get('name') == 'incident' and link.get('to') == 'brd_plannedcase' and link.get('alias')]
    notes_by_case, activities_by_case = {}, {}
    for row in notes or []:
        target = guid(row.get('_objectid_value') or row.get('objectid'))
        notes_by_case.setdefault(target, []).append({'id': guid(row.get('annotationid')), 'title': row.get('subject') or '', 'text': row.get('notetext') or '', 'date': row.get('modifiedon') or row.get('createdon') or ''})
    for row in activities or []:
        target = guid(row.get('_regardingobjectid_value') or row.get('regardingobjectid'))
        activities_by_case.setdefault(target, []).append({'id': guid(row.get('activityid')), 'title': row.get('subject') or '', 'text': row.get('description') or '', 'due': row.get('scheduledend') or '', 'state': row.get('statecode'), 'state_label': label(row, 'statecode')})
    result = {}
    for row in rows:
        identifier = guid(row.get('incidentid'))
        if not identifier:
            raise ValueError('View کیس، شناسه معتبر incidentid برنگرداند؛ دریافت ناقص پذیرفته نشد.')
        parent = guid(row.get('_brd_plannedcase_value') or row.get('brd_plannedcase'))
        parent_status, parent_title = '', label(row, '_brd_plannedcase_value')
        parent_details = {}
        for alias in parent_aliases:
            parent_status = label(row, alias + '.statuscode') or parent_status
            parent_title = label(row, alias + '.title') or parent_title
            parent_details.update({'type': label(row, alias + '.brd_incidenttype'), 'planned_start': row.get(alias + '.brd_plannedstartdate'), 'planned_end': row.get(alias + '.brd_plannedenddate')})
        customer_key = '_brd_account_value' if row.get('_brd_account_value') else '_customerid_value'
        case_notes = sorted(notes_by_case.get(identifier, []), key=lambda n: n['date'], reverse=True)
        result[identifier] = {
            'crm_id': identifier, 'number': str(row.get('ticketnumber') or ''), 'title': row.get('title') or '',
            'customer_id': guid(row.get(customer_key)), 'customer': label(row, customer_key),
            'source_status': label(row, 'statuscode'), 'parent_id': parent, 'parent_title': parent_title, 'parent_status': parent_status,
            'evidence': {'sprint': label(row, '_brd_sprinttime_value') or label(row, 'brd_sprinttime'), 'release': label(row, '_brd_releasetime_value') or label(row, 'brd_releasetime'), 'case_service': label(row, '_brd_caseservice_value') or label(row, 'brd_caseservice'), 'automation_version': label(row, 'sma_upgrade_' + ('brd_account' if customer_key == '_brd_account_value' else 'customerid') + '.brd_automationversion'), 'incident_type': label(row, 'brd_incidenttype'), 'incident_type_code': row.get('brd_incidenttype'), 'case_category': label(row, 'casetypecode'), 'parent_details': parent_details, 'created_on': row.get('createdon'), 'modified_on': row.get('modifiedon'), 'planning_started': row.get('brd_startplanningdate'), 'owner': label(row, '_ownerid_value'), 'state': row.get('statecode'), 'notes': case_notes, 'activities': activities_by_case.get(identifier, []), 'parent_notes': notes_by_case.get(parent, []), 'parent_activities': activities_by_case.get(parent, [])},
        }
    return list(result.values())
