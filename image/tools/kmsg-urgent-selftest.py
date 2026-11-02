#!/usr/bin/env python3
import ast, re, sys
source = open(sys.argv[1]).read()
module = ast.parse(source)
fn = next(node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == 'is_urgent')
ns = {'re': re}
exec(compile(ast.Module(body=[fn], type_ignores=[]), '<urgent>', 'exec'), ns)
urgent = ns['is_urgent']
assert urgent(b'3,1,2,-;error')
assert urgent(b'27,1,2,-;facility error')
for marker in (b'gpu', b'gmu', b'msm', b'arm-smmu', b'adreno', b'qcom_scm', b'power/control', b'runtime', b'panic'):
    assert urgent(b'6,1,2,-;' + marker), marker
assert not urgent(b'6,1,2,-;normal event')
assert not urgent(b'not-a-header;normal event')
print('urgent kmsg classification: PASS')
