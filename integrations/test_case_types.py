from django.test import SimpleTestCase
from integrations.analysis import normalize, FORMAT

class CaseTypeTests(SimpleTestCase):
    def test_type_category_and_parent_are_distinct_source_facts(self):
        row={'incidentid':'11111111-1111-1111-1111-111111111111','brd_incidenttype':1,'brd_incidenttype'+FORMAT:'Issue','casetypecode':42,'casetypecode'+FORMAT:'Bug','parent.brd_incidenttype':2,'parent.brd_incidenttype'+FORMAT:'Backlog','parent.brd_plannedenddate':'2026-10-20'}
        xml='<fetch><entity name="incident"><link-entity name="incident" to="brd_plannedcase" alias="parent"/></entity></fetch>'
        evidence=normalize([row],xml)[0]['evidence']
        self.assertEqual(evidence['incident_type'],'Issue')
        self.assertEqual(evidence['case_category'],'Bug')
        self.assertEqual(evidence['parent_details']['type'],'Backlog')
        self.assertEqual(evidence['parent_details']['planned_end'],'2026-10-20')
        row.pop('brd_incidenttype');row.pop('brd_incidenttype'+FORMAT)
        self.assertEqual(normalize([row],xml)[0]['evidence']['incident_type'],'')
