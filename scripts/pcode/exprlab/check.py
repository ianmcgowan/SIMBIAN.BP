import glob, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))+'/..')
from ud import container, decompile
exp = {
 'vv_add':'X = P + Q','vc_add':'X = P + 3','cv_add':'X = 3 + P','cc_add':'X = 3 + 4',
 'vv_sub':'X = P - Q','vv_mul':'X = P * Q','vv_div':'X = P / Q','vv_cat':'X = P : Q',
 'vc_cat':"X = P : 'z'",'vv_pwr':'X = P ^ Q',
 'vv_eq':'X = P = Q','vc_eq':'X = P = 3','vv_lt':'X = P < Q','vv_ne':'X = P # Q',
 'vv_gt':'X = P > Q','vv_le':'X = P <= Q','vv_ge':'X = P >= Q',
 'vvv_add':'X = P + Q + R','vvv_sub':'X = P - Q - R','vvc_add':'X = P + Q + 3',
 'cvv_add':'X = 3 + P + Q','vcv_add':'X = P + 3 + Q',
 'vvv_mix1':'X = P + Q * R','vvv_mix2':'X = P * Q + R','vvv_paren':'X = (P + Q) * R',
 'vvvv_add':'X = P + Q + R + S',
 'neg_v':'X = -P','neg_c':'X = -3','not_v':'X = NOT(P)',
 'fn1':'X = LEN(P)','fn1c':"X = LEN('abcd')",'fn2':"X = OCONV(P, 'MCU')",
 'fn3':"X = FIELD(P, ',', 2)",'fn_nest':'X = LEN(TRIM(P))','fn_arg_expr':'X = LEN(P : Q)',
 'fn_plus_v':'X = LEN(P) + Q','v_plus_fn':'X = Q + LEN(P)',
 'fn_trim':'X = TRIM(P)','fn_upcase':'X = UPCASE(P)','fn_count':"X = COUNT(P, ',')",
 'fn_index':"X = INDEX(P, 'x', 1)",'fn_num':'X = NUM(P)','fn_seq':'X = SEQ(P)',
 'fn_str':"X = STR('x', 5)",'fn_space':'X = SPACE(4)',
 'if_vc_eq':'IF P = 3','if_vv_eq':'IF P = Q','if_vv_gt':'IF P > Q','if_vv_lt':'IF P < Q',
 'if_vv_ne':'IF P # Q','if_vv_ge':'IF P >= Q','if_expr':'IF P + Q > 10',
 'if_and':'IF P = 3 AND Q = 4','if_or':'IF P = 3 OR Q = 4',
}
ok=bad=0
for fn in sorted(glob.glob(os.path.join(os.path.dirname(__file__),'obj','_*'))):
    name=os.path.basename(fn)[1:]
    if name not in exp: continue
    c=container.load(open(fn,'rb').read())
    txt=decompile.decompile_text(c)
    got=None
    for ln in txt.splitlines():
        core = ln.split('|',1)[1].strip() if '|' in ln else ''
        if core.startswith(('X =','IF ')) and got is None:
            got = core
    want=exp[name]
    # normalise: our IF emits "IF cond THEN GOTO ..." -> compare prefix
    g = got or ''
    if g.startswith('IF '):
        g = g.split(' THEN')[0].strip()
    # strip our advisory ;* comments
    g = g.split('   ;*')[0].strip()
    match = (g == want)
    print(f"{'OK ' if match else 'XX '} {name:12} want={want!r:34} got={got!r}")
    ok+= match; bad+= (not match)
print(f"\n{ok}/{ok+bad} exact")
