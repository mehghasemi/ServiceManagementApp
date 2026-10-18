"""Allowlisted ordering before pagination; missing values always last."""
import re

def value_at(row, path):
    for part in path.split('.'):
        row = row.get(part) if isinstance(row, dict) else getattr(row, part, None)
        if row is None: break
    return row

def sort_rows(request, rows, fields):
    field = fields.get(request.GET.get('sort'))
    if not field: return rows
    pairs = [(row, value_at(row, field)) for row in rows]
    known = [(row, value) for row, value in pairs if value is not None and value != '']
    def key(pair):
        value = pair[1]
        if isinstance(value, (int, float)): return (0, value)
        text = str(value).casefold().replace('ي','ی').replace('ك','ک')
        return (1, tuple((0, int(p)) if p.isdigit() else (1, p) for p in re.split(r'(\d+)', text)))
    known.sort(key=key, reverse=request.GET.get('direction') == 'desc')
    return [row for row, _ in known] + [row for row, value in pairs if value is None or value == '']
