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
    locals_fun: list[WasmId] = [WasmId('$%'+k.name) for k in vars.funLocals.keys()]
    table = WasmFuncTable(locals_fun)
    fun_intrs = compileFunDefs(m.funs, cfg, table, vars.funLocals)
    la_array, ctx=fun_transform.transStmts(stmts=m.stmts, ctx=ctx)
    wasm_instrs = compileStmts(la_array, cfg, table)
    locals_temp: list[tuple[WasmId, WasmValtype]] = [(identToWasmId(k), 'i64' if type(v)==Int else 'i32') for k, v in ctx.freshVars.items()]
    locals_var: list[tuple[WasmId, WasmValtype]] = [(identToWasmId(x.name), 'i64' if type(x.ty)==Int else 'i32') for x in vars.toplevelLocals]

    module = WasmModule(wasmImports(cfg.maxMemSize),
                        [WasmExport('main', WasmExportFunc(WasmId('$main')))],
                        Globals.decls(),
                        [WasmData(start=1, content="True"), WasmData(start=0, content="False")] + Errors.data(),
                        table,
                        [WasmFunc(WasmId('$main'), [], None, locals_temp + locals_var + Locals.decls(), wasm_instrs)] + fun_intrs)

    return module

def compileFunDefs(funs: list[PlainAst.fun], cfg: CompilerConfig, table: WasmFuncTable, funLocals: dict[ident, list[fun_tychecker.LocalVar]]) -> list[WasmFunc]:
    wasm_instrs: list[WasmFunc] = []
    for fun in funs:
        match fun.result:
            case Void():
                res_ty = None
            case NotVoid(ty):
                res_ty = 'i64' if type(ty)==Int else 'i32'
        la_funs, ctx = fun_transform.transStmts(fun.body, fun_transform.Ctx())
        fun_locals_1: list[tuple[WasmId, WasmValtype]] = [(identToWasmId(k), 'i64' if type(v)==Int else 'i32') for k, v in ctx.freshVars.items()] # type: ignore
        fun_locals_2: list[tuple[WasmId, WasmValtype]] = [(identToWasmId(x.name), 'i64' if type(x.ty)==Int else 'i32') for x in funLocals[fun.name]]
        func_instrs = WasmInstrBlock(WasmId("$fun_exit"), res_ty, compileStmts(la_funs, cfg, table) + [WasmInstrConst(res_ty if res_ty is not None else 'i32', 0)])
        wasm_instrs.append(WasmFunc(WasmId('$%'+fun.name.name), [(identToWasmId(x.var), 'i64' if type(x.ty)==Int else 'i32') for x in fun.params], res_ty, fun_locals_1 + fun_locals_2 + Locals.decls(), [func_instrs]))
    return wasm_instrs

def compileStmts(stmts: list[stmt], cfg: CompilerConfig, table: WasmFuncTable) -> list[WasmInstr]:
    wasm_instrs: list[WasmInstr] = []
    for stmt in stmts:
        match stmt:
            case Assign(x, e):
                wasm_instrs.extend(compileExp(e, cfg, table)+[WasmInstrVarLocal(op='set', id=identToWasmId(x))])
            case StmtExp(e):
                wasm_instrs.extend(compileExp(e, cfg, table))
            case IfStmt(cond, tb, eb):
                # wasm_instrs+=compileExp(cond, cfg)+[WasmInstrIf(resultType='i32', thenInstrs=compileStmts(tb, cfg)+[WasmInstrConst(ty='i32', val=0)], elseInstrs=compileStmts(eb, cfg)+[WasmInstrConst(ty='i32', val=0)])]+[WasmInstrDrop()]
                wasm_instrs += compileExp(cond, cfg, table) + [WasmInstrIf(resultType=None, thenInstrs=compileStmts(tb, cfg, table), elseInstrs=compileStmts(eb, cfg, table))]
            case WhileStmt():
                wasm_instrs.extend(compileWhileStmt(stmt, cfg, table))
            case SubscriptAssign(l, i, r):
                wasm_instrs.extend(arrayOffsetInstrs(l, i, cfg, table))
                wasm_instrs.extend(compileExp(r, cfg, table))
                match r:
                    case AtomExp():
                        wasm_instrs.extend([WasmInstrMem(ty='i64', op='store')])
                    case _:
                        wasm_instrs.extend([WasmInstrMem(ty='i32', op='store')])
            case Return(res):
                if res is not None and res.ty != Void():
                    wasm_instrs.extend(compileExp(res, cfg, table))
                    wasm_instrs.append(WasmInstrBranch(WasmId("$fun_exit"), False))
    return wasm_instrs

def compileWhileStmt(stmt: WhileStmt, cfg: CompilerConfig, table: WasmFuncTable) -> list[WasmInstr]:
    start_label = WasmId('$loop_start')
    end_label = WasmId('$loop_end')

    cond_instrs = compileExp(stmt.cond, cfg, table)
    body_instrs = compileStmts(stmt.body, cfg, table)

    instrs : list[WasmInstr] = [
        WasmInstrBlock(
            label=end_label, 
            result=None, 
            body=[
                WasmInstrLoop(
                    label=start_label, 
                    body=cond_instrs + [
                        WasmInstrIf(
                            resultType=None, 
                            thenInstrs=body_instrs + [WasmInstrBranch(target=start_label, conditional=False)], 
                            elseInstrs=[WasmInstrBranch(target=end_label, conditional=False)]
                        )
                    ]
                )
            ]
        )
    ]

    return instrs

def compileExpStmt(stmt: StmtExp, cfg: CompilerConfig, table: WasmFuncTable) -> list[WasmInstr]:
    wasm_instrs: list[WasmInstr] = []
    wasm_instrs.extend(compileExp(stmt.exp, cfg, table))
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

def compileExp(e: exp | AtomExp, cfg: CompilerConfig, table: WasmFuncTable) -> list[WasmInstr]:
    wasm_instrs: list[WasmInstr] = []
    match e:
        case ArrayInitDyn():
            element_size = 8 if isinstance(tyOfExp(e), Int) else 4
            wasm_instrs.extend(compileInitArray(e.len, tyOfExp(e), cfg, table))
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
                                                 + compileExp(AtomExp(e.elemInit, ty=e.ty), cfg, table)
                                                 + [store_command]
                                                 + [WasmInstrVarLocal('get', WasmId('$@tmp_i32')),
                                                    WasmInstrConst('i32', element_size), WasmInstrNumBinOp('i32', 'add'),
                                                    WasmInstrVarLocal('set', WasmId('$@tmp_i32')), WasmInstrBranch(loop_label_start, conditional=False)]
                                                 )
            ]))
        case ArrayInitStatic(elemInit):
            elemTy=tyOfExp(e)
            wasm_instrs.extend(compileInitArray(lenExp=IntConst(len(elemInit), ty=Int()), elemTy=elemTy, cfg=cfg, table=table))
            offset=4
            wasm_instrs.extend([WasmInstrVarLocal(op='tee', id=WasmId(id='$@tmp_i32'))])
            for elem in elemInit:
                wasm_instrs.extend([WasmInstrVarLocal(op='get', id=WasmId(id='$@tmp_i32'))])
                wasm_instrs.extend([WasmInstrConst(ty='i32', val=offset), WasmInstrNumBinOp(ty='i32', op='add'), compileAtomExp(elem, table)])
                match elemTy:
                    case Int():
                        wasm_instrs.extend([WasmInstrMem(ty='i64', op='store')])
                        offset+=8
                    case _:
                        wasm_instrs.extend([WasmInstrMem(ty='i32', op='store')])
                        offset+=4
        case Subscript():
            wasm_instrs.extend(arrayOffsetInstrs(e.array, e.index, cfg, table))
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
            wasm_instrs.append(compileAtomExp(x, table))
        case Call(id, args):
            for arg in args:
                wasm_instrs.extend(compileExp(arg, cfg, table))
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
                case CallTargetDirect(var):
                    wasm_instrs.append(WasmInstrCall(WasmId(f'$%{var.name}')))
                case CallTargetIndirect(var, params, result):
                    wasm_instrs.append(WasmInstrVarLocal('get', identToWasmId(var)))
                    wasm_instrs.append(WasmInstrCallIndirect(params=['i64' if p==Int() else 'i32' for p in params], result='i64' if result.ty==Int() else 'i32'))  # type: ignore
        case UnOp(op, sub):
            wasm_instrs.extend(compileExp(sub, cfg, table))
            match op:
                case USub():
                    wasm_instrs.append(WasmInstrConst('i64', -1))
                    wasm_instrs.append(WasmInstrNumBinOp('i64', 'mul'))
                case Not():
                    wasm_instrs.append(WasmInstrConst('i32', 1))
                    wasm_instrs.append(WasmInstrNumBinOp('i32', 'sub'))
        case BinOp(left, op, right):
            if op != And() and op != Or():
                wasm_instrs.extend(compileExp(left, cfg, table))
                wasm_instrs.extend(compileExp(right, cfg, table))
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
                wasm_instrs.extend(compileExp(left, cfg, table))
                match op:
                    case And():
                        wasm_instrs.append(WasmInstrIf('i32', compileExp(right, cfg, table), [WasmInstrConst('i32', 0)]))
                    case Or():
                        wasm_instrs.append(WasmInstrIf('i32', [WasmInstrConst('i32', 1)], compileExp(right, cfg, table)))
                    case _:
                        pass
    return wasm_instrs

def identToWasmId(identifier: ident) -> WasmId:
    return WasmId('$' + identifier.name)

def compileAtomExp(e: atomExp, table: WasmFuncTable) -> WasmInstr:
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
            return WasmInstrVarLocal(op='get', id=identToWasmId(x))
        case FunName(x):
            if "tmp" in x.name:
                return WasmInstrVarLocal(op='get', id=identToWasmId(x))
            else:
                return WasmInstrConst(ty='i32', val=table.get_index_of_func(WasmId("$%" + x.name)))

def compileInitArray(lenExp: atomExp, elemTy: ty, cfg: CompilerConfig, table: WasmFuncTable) -> list[WasmInstr]:
    instrs: list[WasmInstr]=[]
    length = compileAtomExp(lenExp, table)

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

def arrayOffsetInstrs(arrayExp: atomExp, indexExp: atomExp, cfg: CompilerConfig, table: WasmFuncTable)-> list[WasmInstr]:
    wasm_instrs: list[WasmInstr] = []
    wasm_instrs.extend(compileExp(AtomExp(arrayExp, NotVoid(arrayExp.ty)), cfg, table))
    wasm_instrs.extend(arrayLenInstrs())
    wasm_instrs.append(WasmInstrConvOp('i32.wrap_i64'))
    wasm_instrs.extend(compileExp(AtomExp(indexExp, NotVoid(arrayExp.ty)), cfg, table))
    wasm_instrs.append(WasmInstrConvOp('i32.wrap_i64'))
    wasm_instrs.append(WasmInstrIntRelOp('i32', 'le_u'))
    wasm_instrs.append(WasmInstrIf('i32', 
                                   Errors.outputError(Errors.arrayIndexOutOfBounds) + [WasmInstrTrap()],
                                   [WasmInstrConst('i32', 0)]))
    wasm_instrs.append(WasmInstrDrop())
    wasm_instrs.extend(compileExp(AtomExp(arrayExp, NotVoid(arrayExp.ty)), cfg, table))
    wasm_instrs.extend(compileExp(AtomExp(indexExp, NotVoid(indexExp.ty)), cfg, table))
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