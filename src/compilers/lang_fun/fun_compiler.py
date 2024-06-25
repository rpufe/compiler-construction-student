from lang_fun.fun_astAtom import *
import lang_fun.fun_ast as PlainAst
from common.wasm import *
import lang_fun.fun_tychecker as fun_tychecker
import compilers.lang_fun.fun_transform as fun_transform
from lang_array.array_compilerSupport import *
from common.compilerSupport import *

def compileModule(m: PlainAst.mod, cfg: CompilerConfig) -> WasmModule:
    vars = fun_tychecker.tycheckModule(m)
    ctx=fun_transform.Ctx()
    la_array=fun_transform.transStmts(stmts=m.stmts, ctx=ctx)
    wasm_instrs = compileStmts(la_array, cfg)
    locals_temp: list[tuple[WasmId, WasmValtype]] = [(identToWasmId(k), 'i64' if type(v)==Int else 'i32') for k, v in ctx.freshVars.items()]
    locals_var: list[tuple[WasmId, WasmValtype]] = [(identToWasmId(x.name), 'i64' if type(x.ty)==Int else 'i32') for x in vars.toplevelLocals]

    module = WasmModule(wasmImports(cfg.maxMemSize),
                        [WasmExport('main', WasmExportFunc(WasmId('$main')))],
                        Globals.decls(),
                        [WasmData(start=1, content="True"), WasmData(start=0, content="False")] + Errors.data(),
                        WasmFuncTable([]),
                        [WasmFunc(WasmId('$main'), [], None, locals_temp + locals_var + Locals.decls(), wasm_instrs)])

    return module

def compileStmts(stmts: list[stmt], cfg: CompilerConfig) -> list[WasmInstr]:
    wasm_instrs: list[WasmInstr] = []
    for stmt in stmts:
        match stmt:
            case Assign(x, e):
                wasm_instrs.extend(compileExp(e, cfg)+[WasmInstrVarLocal(op='set', id=WasmId(id=f'${x.name}'))])
            case StmtExp(e):
                wasm_instrs.extend(compileExp(e, cfg))
            case IfStmt(cond, tb, eb):
                wasm_instrs+=compileExp(cond, cfg)+[WasmInstrIf(resultType='i32', thenInstrs=compileStmts(tb, cfg)+[WasmInstrConst(ty='i32', val=0)], elseInstrs=compileStmts(eb, cfg)+[WasmInstrConst(ty='i32', val=0)])]+[WasmInstrDrop()]
            case WhileStmt():
                wasm_instrs.extend(compileWhileStmt(stmt, cfg))
            case SubscriptAssign(l, i, r):
                wasm_instrs.extend(arrayOffsetInstrs(l, i, cfg))
                wasm_instrs.extend(compileExp(r, cfg))
                match r:
                    case AtomExp():
                        wasm_instrs.extend([WasmInstrMem(ty='i64', op='store')])
                    case _:
                        wasm_instrs.extend([WasmInstrMem(ty='i32', op='store')])
            case Return(res):
                if res is not None and res.ty != Void():
                    wasm_instrs.extend(compileExp(res, cfg))
                    wasm_instrs.append(WasmInstrBranch(WasmId("$fun_exit"), False))
    return wasm_instrs

def compileWhileStmt(stmt: WhileStmt, cfg: CompilerConfig) -> list[WasmInstr]:
    wasm_instrs: list[WasmInstr] = []
    loop_label_start = WasmId('$loop_start')
    loop_label_exit = WasmId('$loop_exit')
    wasm_instrs.append(WasmInstrBlock(loop_label_exit, None, [
        WasmInstrLoop(loop_label_start, compileExp(stmt.cond, cfg) + 
            [WasmInstrIf('i32',
                        compileStmts(stmt.body, cfg) + [WasmInstrBranch(loop_label_start, conditional=False)],
                        [WasmInstrBranch(loop_label_exit, conditional=False)])
                        ] + [WasmInstrDrop()])
    ]))
    return wasm_instrs

def compileExpStmt(stmt: StmtExp, cfg: CompilerConfig) -> list[WasmInstr]:
    wasm_instrs: list[WasmInstr] = []
    wasm_instrs.extend(compileExp(stmt.exp, cfg))
    return wasm_instrs

def tyOfExp(e: exp)-> ty:
    match e.ty:
        # case None:
        #     raise ValueError()
        case Void():
            raise ValueError()
        case NotVoid(rty):
            match rty:
                case Array():
                    return rty.elemTy
                case _:
                    return rty

def compileExp(e: exp | AtomExp, cfg: CompilerConfig) -> list[WasmInstr]:
    wasm_instrs: list[WasmInstr] = []
    match e:
        case ArrayInitDyn():
            element_size = 8 if isinstance(tyOfExp(e), Int) else 4
            wasm_instrs.extend(compileInitArray(e.len, tyOfExp(e), cfg))
            wasm_instrs.append(WasmInstrVarLocal('tee', WasmId('$@tmp_i32')))
            wasm_instrs.append(WasmInstrVarLocal('get', WasmId('$@tmp_i32')))
            wasm_instrs.append(WasmInstrConst('i32', 4))
            wasm_instrs.append(WasmInstrNumBinOp('i32', 'add'))
            wasm_instrs.append(WasmInstrVarLocal('set', WasmId('$@tmp_i32')))
            loop_label_start = WasmId('$loop_start')
            loop_label_exit = WasmId('$loop_exit')
            if type(tyOfExp(e)) == Array or type(tyOfExp(e)) == Bool:
                store_command = WasmInstrMem('i32', 'store')
            else:
                store_command = WasmInstrMem('i64', 'store')
            wasm_instrs.append(WasmInstrBlock(loop_label_exit, None, [
                WasmInstrLoop(loop_label_start, [WasmInstrVarLocal('get', WasmId('$@tmp_i32')),
                                                 WasmInstrVarGlobal('get', Globals.freePtr),
                                                 WasmInstrIntRelOp('i32', 'lt_u'),
                                                 WasmInstrIf('i32', [WasmInstrConst('i32', 0)], [WasmInstrBranch(loop_label_exit, conditional=False)]),
                                                 WasmInstrDrop(),
                                                 WasmInstrVarLocal('get', WasmId('$@tmp_i32'))]
                                                 + compileExp(AtomExp(e.elemInit, ty=e.ty), cfg)
                                                 + [store_command]
                                                 + [WasmInstrVarLocal('get', WasmId('$@tmp_i32')),
                                                    WasmInstrConst('i32', element_size), WasmInstrNumBinOp('i32', 'add'),
                                                    WasmInstrVarLocal('set', WasmId('$@tmp_i32')), WasmInstrBranch(loop_label_start, conditional=False)]
                                                 )
            ]))
        case ArrayInitStatic(elemInit):
            elemTy=tyOfExp(e)
            wasm_instrs.extend(compileInitArray(lenExp=IntConst(len(elemInit), ty=Int()), elemTy=elemTy, cfg=cfg))
            offset=4
            wasm_instrs.extend([WasmInstrVarLocal(op='tee', id=WasmId(id='$@tmp_i32'))])
            for elem in elemInit:
                wasm_instrs.extend([WasmInstrVarLocal(op='get', id=WasmId(id='$@tmp_i32'))])
                wasm_instrs.extend([WasmInstrConst(ty='i32', val=offset), WasmInstrNumBinOp(ty='i32', op='add'), compileAtomExp(elem)])
                match elemTy:
                    case Int():
                        wasm_instrs.extend([WasmInstrMem(ty='i64', op='store')])
                        offset+=8
                    case _:
                        wasm_instrs.extend([WasmInstrMem(ty='i32', op='store')])
                        offset+=4
        case Subscript():
            wasm_instrs.extend(arrayOffsetInstrs(e.array, e.index, cfg))
            match e.ty:
                # case None:
                #     raise ValueError()
                case Void():
                    raise ValueError()
                case NotVoid(rty):
                    match rty:
                        case Int():
                            wasm_instrs.append(WasmInstrMem('i64', 'load'))
                        case _:
                            wasm_instrs.append(WasmInstrMem('i32', 'load'))
        case AtomExp(x):
            wasm_instrs.append(compileAtomExp(x))
        case Call(id, args):
            for arg in args:
                wasm_instrs.extend(compileExp(arg, cfg))
            match id:
                case CallTargetBuiltin(var):
                    if "print" in var.name:
                        match tyOfExp(args[0]):
                            case Bool():
                                wasm_instrs.append(WasmInstrCall(WasmId(f'${var.name.split("_")[0]}_bool')))
                            case Int():
                                wasm_instrs.append(WasmInstrCall(WasmId(f'${var.name.split("_")[0]}_i64')))
                            case _:
                                pass
                    elif "input" in var.name:
                        wasm_instrs.append(WasmInstrCall(WasmId(f'${var.name.split("_")[0]}_i64')))
                    elif "len" in var.name:
                        wasm_instrs.extend(arrayLenInstrs())
                case CallTargetDirect():
                    pass
                case CallTargetIndirect():
                    pass
        case UnOp(op, sub):
            wasm_instrs.extend(compileExp(sub, cfg))
            match op:
                case USub():
                    wasm_instrs.append(WasmInstrConst('i64', -1))
                    wasm_instrs.append(WasmInstrNumBinOp('i64', 'mul'))
                case Not():
                    wasm_instrs.append(WasmInstrConst('i32', 1))
                    wasm_instrs.append(WasmInstrNumBinOp('i32', 'sub'))
        case BinOp(left, op, right):
            if op != And() and op != Or():
                wasm_instrs.extend(compileExp(left, cfg))
                wasm_instrs.extend(compileExp(right, cfg))
                match op:
                    case Is():
                        wasm_instrs.append(WasmInstrIntRelOp('i32', 'eq'))
                    case Add():
                        wasm_instrs.append(WasmInstrNumBinOp('i64', 'add'))
                    case Sub():
                        wasm_instrs.append(WasmInstrNumBinOp('i64', 'sub'))
                    case Mul():
                        wasm_instrs.append(WasmInstrNumBinOp('i64', 'mul'))
                    case LessEq():
                        wasm_instrs.append(WasmInstrIntRelOp('i64', 'le_s'))
                    case Less():
                        wasm_instrs.append(WasmInstrIntRelOp('i64', 'lt_s'))
                    case Greater():
                        wasm_instrs.append(WasmInstrIntRelOp('i64', 'gt_s'))
                    case GreaterEq():
                        wasm_instrs.append(WasmInstrIntRelOp('i64', 'ge_s'))
                    case Eq():
                        match tyOfExp(left):
                            case Bool():
                                wasm_instrs.append(WasmInstrIntRelOp('i32', 'eq'))
                            case Int():
                                wasm_instrs.append(WasmInstrIntRelOp('i64', 'eq'))
                            case _:
                                pass
                    case NotEq():
                        match tyOfExp(left):
                            case Bool():
                                wasm_instrs.append(WasmInstrIntRelOp('i32', 'ne'))
                            case Int():
                                wasm_instrs.append(WasmInstrIntRelOp('i64', 'ne'))
                            case _:
                                pass
                    case _:
                        pass
            else:
                wasm_instrs.extend(compileExp(left, cfg))
                match op:
                    case And():
                        wasm_instrs.append(WasmInstrIf('i32', compileExp(right, cfg), [WasmInstrConst('i32', 0)]))
                    case Or():
                        wasm_instrs.append(WasmInstrIf('i32', [WasmInstrConst('i32', 1)], compileExp(right, cfg)))
                    case _:
                        pass
    return wasm_instrs

def identToWasmId(identifier: ident) -> WasmId:
    return WasmId('$' + identifier.name)

def compileAtomExp(e: atomExp) -> WasmInstr:
    match e:
        case IntConst(n):
            return WasmInstrConst(ty='i64', val=n)
        case BoolConst(n):
            match n:
                case True:
                    return WasmInstrConst(ty='i32', val=1)
                case False:
                    return WasmInstrConst(ty='i32', val=0)
        case VarName(x):
            return WasmInstrVarLocal(op='get', id=WasmId(id=f'${x.name}'))
        case FunName(x):
            return WasmInstrVarLocal(op='get', id=WasmId(id=f'${x.name}'))

def compileInitArray(lenExp: atomExp, elemTy: ty, cfg: CompilerConfig) -> list[WasmInstr]:
    instrs: list[WasmInstr]=[]
    length = compileAtomExp(lenExp)

    # check length
    instrs+=[length]
    match elemTy:
        case Int():
            instrs.extend([WasmInstrConst(ty='i64', val=8)])
        case _:
            instrs.extend([WasmInstrConst(ty='i64', val=4)])
    instrs.extend([WasmInstrNumBinOp('i64', 'mul'), WasmInstrConst(ty='i64', val=cfg.maxArraySize), WasmInstrIntRelOp(ty='i64', op='gt_s')])
    instrs.extend([WasmInstrIf(resultType='i32', thenInstrs=Errors.outputError(Errors.arraySize)+[WasmInstrTrap()], elseInstrs=[WasmInstrConst(ty='i32', val=0)]), WasmInstrDrop()])
    instrs.extend([length, WasmInstrConst(ty='i64', val=0), WasmInstrIntRelOp(ty='i64', op='lt_s')])
    instrs.extend([WasmInstrIf(resultType='i32', thenInstrs=Errors.outputError(Errors.arraySize)+[WasmInstrTrap()], elseInstrs=[WasmInstrConst(ty='i32', val=0)]), WasmInstrDrop()])
    # compute and store header
    instrs.extend([WasmInstrVarGlobal(op='get', id=WasmId(id='$@free_ptr'))])
    instrs.extend([length])
    instrs.extend([WasmInstrConvOp('i32.wrap_i64')])
    instrs.extend([WasmInstrConst(ty='i32', val=4), WasmInstrNumBinOp(ty='i32', op='shl')])
    instrs.extend([WasmInstrConst(ty='i32', val=1)])
    instrs.extend([WasmInstrNumBinOp(ty='i32', op='xor'), WasmInstrMem(ty='i32', op='store')])
    # move $@free_ptr and return array address
    instrs.extend([WasmInstrVarGlobal(op='get', id=WasmId(id='$@free_ptr'))])
    instrs.extend([length])
    instrs.extend([WasmInstrConvOp('i32.wrap_i64')])
    match elemTy:
        case Int():
            instrs.extend([WasmInstrConst(ty='i32', val=8)])
        case _:
            instrs.extend([WasmInstrConst(ty='i32', val=4)])
    instrs.extend([WasmInstrNumBinOp(ty='i32', op='mul'), WasmInstrConst(ty='i32', val=4), WasmInstrNumBinOp(ty='i32', op='add')])
    instrs.extend([WasmInstrVarGlobal(op='get', id=WasmId(id='$@free_ptr')), WasmInstrNumBinOp(ty='i32', op='add'), WasmInstrVarGlobal(op='set', id=WasmId(id='$@free_ptr'))])

    return instrs

def arrayLenInstrs() -> list[WasmInstr]:
    return [WasmInstrMem('i32', 'load'), WasmInstrConst('i32', 4), WasmInstrNumBinOp('i32', 'shr_u'), WasmInstrConvOp('i64.extend_i32_u')]

def arrayOffsetInstrs(arrayExp: atomExp, indexExp: atomExp, cfg: CompilerConfig)-> list[WasmInstr]:
    wasm_instrs: list[WasmInstr] = []
    wasm_instrs.extend(compileExp(AtomExp(arrayExp, NotVoid(arrayExp.ty)), cfg))
    wasm_instrs.extend(arrayLenInstrs())
    wasm_instrs.append(WasmInstrConvOp('i32.wrap_i64'))
    wasm_instrs.extend(compileExp(AtomExp(indexExp, NotVoid(arrayExp.ty)), cfg))
    wasm_instrs.append(WasmInstrConvOp('i32.wrap_i64'))
    wasm_instrs.append(WasmInstrIntRelOp('i32', 'le_u'))
    wasm_instrs.append(WasmInstrIf('i32', 
                                   Errors.outputError(Errors.arrayIndexOutOfBounds) + [WasmInstrTrap()],
                                   [WasmInstrConst('i32', 0)]))
    wasm_instrs.append(WasmInstrDrop())
    wasm_instrs.extend(compileExp(AtomExp(arrayExp, NotVoid(arrayExp.ty)), cfg))
    wasm_instrs.extend(compileExp(AtomExp(indexExp, NotVoid(indexExp.ty)), cfg))
    wasm_instrs.append(WasmInstrConvOp('i32.wrap_i64'))
    if isinstance(arrayExp.ty.elemTy, Int): # type: ignore
        wasm_instrs.append(WasmInstrConst('i32', 8))
    else:
        wasm_instrs.append(WasmInstrConst('i32', 4))
    wasm_instrs += [
        WasmInstrNumBinOp('i32', 'mul'),
        WasmInstrConst('i32', 4),
        WasmInstrNumBinOp('i32', 'add'),
        WasmInstrNumBinOp('i32', 'add')
    ]
    return wasm_instrs