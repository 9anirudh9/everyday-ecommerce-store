"""Remove guest capability cookies from retained test diagnostics and traces."""
import json
import re
import zipfile


def redact_text(text):
    text=re.sub(r'(__Host-everyday-guest=)[a-f0-9]{64}',r'\1<redacted>',text)
    return re.sub(r'guest:[a-f0-9]{64}','guest:<redacted>',text)


def redact(value):
    if isinstance(value,dict):
        result={key:redact(item) for key,item in value.items()}
        if result.get('name')=='__Host-everyday-guest' and 'value' in result:
            result['value']='<redacted>'
        return result
    if isinstance(value,list):return [redact(item) for item in value]
    return redact_text(value) if isinstance(value,str) else value


def redact_trace(path):
    temporary=path.with_suffix('.redacted.zip')
    with zipfile.ZipFile(path) as source,zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED) as target:
        for info in source.infolist():
            data=source.read(info.filename)
            try:
                text=data.decode('utf-8')
                lines=[]
                for line in text.splitlines():
                    try:lines.append(json.dumps(redact(json.loads(line)),ensure_ascii=False))
                    except (ValueError,TypeError):lines.append(redact_text(line))
                data=('\n'.join(lines)+('\n' if text.endswith('\n') else '')).encode('utf-8')
            except UnicodeDecodeError:pass
            target.writestr(info,data)
    temporary.replace(path)
