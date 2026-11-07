"""Usage: uv run --with tokenizers measure.py /path/to/DeepSeek-V4.1-Flash/tokenizer.json"""
from pathlib import Path
import hashlib
import json
import sys
from tokenizers import Tokenizer

source = Path(sys.argv[1]).read_bytes()
blob = hashlib.sha1(b'blob ' + str(len(source)).encode() + b'\0' + source).hexdigest()
assert blob == '6a15814dd25c934028034531da744c689f87ff21'
tokenizer = Tokenizer.from_str(source.decode())
samples = {}
for text in ['王二讲 Agent 开源了吗？', '𠮷', '人工智能', '大模型']:
    ids = tokenizer.encode(text, add_special_tokens=False).ids
    assert tokenizer.decode(ids) == text
    samples[text] = dict(ids=ids, parts=[tokenizer.decode([i]) for i in ids],
                         utf8=list(text.encode()), decoded=tokenizer.decode(ids))
data = dict(model='DeepSeek-V4.1-Flash', revision='314113f8a7dadb388215396ba5fbee2c610a04d6',
            tokenizer_blob=blob, base_vocab=len(json.loads(source)['model']['vocab']), samples=samples)
Path(__file__).with_name('results.json').write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')
