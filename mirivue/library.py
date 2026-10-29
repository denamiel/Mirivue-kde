from .i18n import tr
tr('Local, versioned JSON state. No executable data is deserialized.')
import json
from dataclasses import asdict, fields
from pathlib import Path
from datetime import datetime
from .metadata import Video

def stamp():
    return datetime.now().astimezone().isoformat(timespec=tr('seconds'))

def encode_row(row):
    data = asdict(row)
    data[tr('path')] = str(row.path)
    return data

def decode_row(data):
    if not isinstance(data, dict):
        raise ValueError(tr('Entrée invalide'))
    data = {k: v for k, v in data.items() if k in {f.name for f in fields(Video)}}
    data[tr('path')] = Path(data[tr('path')])
    # Column 13 is an intentionally retired compatibility slot.  Keeping its
    # position avoids shifting every newer saved column while ensuring an old
    # cached label can never reappear.
    for key, empty in ((tr('values'), ''), (tr('sort_values'), -1)):
        cells = data.get(key)
        if isinstance(cells, list) and len(cells) > 13:
            cells[13] = empty
    for key in (tr('file_signature'), tr('bitrate_result'), tr('companion_signature')):
        if data.get(key) is not None:
            data[key] = tuple(data[key])
    dates = data.get(tr('analysis_dates'))
    if isinstance(dates, dict):
        retained = {tr('duration'), tr('duplicates')}
        data[tr('analysis_dates')] = {key: value for key, value in dates.items() if key in retained}
    if tr('original_bitrate') not in data:
        rates = data.get(tr('sort_values'), [])
        data[tr('original_bitrate')] = rates[6] if len(rates) > 6 and rates[6] > 0 and (data.get(tr('bitrate_saved')) or not data.get(tr('bitrate_result'))) else None
    return Video(**data)

def read(settings, key, default):
    store = getattr(settings, tr('_mirivue_store'), None)
    if store and key in store.latest:
        return store.latest[key]
    try:
        return json.loads(settings.value('library-v1/' + key, json.dumps(default)))
    except (ValueError, TypeError):
        return default

def write(settings, key, value):
    store = getattr(settings, tr('_mirivue_store'), None)
    large = key in (tr('results'), tr('duplicates')) and len(value) > 128 or (key in (tr('pending'), tr('history')) and sum((len(j.get(tr('rows'), [])) for j in value)) > 128)
    if large or store:
        if store is None:
            from .responsive import DeferredStore
            store = DeferredStore(settings)
            settings._mirivue_store = store
            owner = settings.parent()
            if owner is not None and hasattr(owner, tr('report_store_error')):
                store.failed.connect(owner.report_store_error)
        store.put(key, dict(value) if isinstance(value, dict) else list(value))
    else:
        settings.setValue('library-v1/' + key, json.dumps(value, ensure_ascii=False))
        settings.sync()

def job_data(job):
    return {k: v for k, v in dict(kind=job[tr('kind')], samples=job[tr('samples')], label=job[tr('label')], rows=[job.get(tr('_encoded'), {}).get(r.path) or encode_row(r) for r in job[tr('rows')]], done=[str(p) for p in job[tr('done')]], errors=list(job[tr('errors')]), state=job[tr('state')], message=job[tr('message')], date=job.get(tr('date'), stamp())).items() if v is not None}

def restore_job(data):
    if data[tr('kind')] not in (tr('duplicates'), tr('duration')):
        raise ValueError(tr('Opération inconnue'))
    rows = [decode_row(r) for r in data[tr('rows')]]
    return dict(data, _encoded={r.path: encoded for r, encoded in zip(rows, data[tr('rows')])}, rows=rows, paths={r.path for r in rows}, done={Path(p) for p in data.get(tr('done'), [])}, started=set())
