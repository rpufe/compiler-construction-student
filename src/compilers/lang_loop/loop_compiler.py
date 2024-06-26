from lang_loop.loop_ast import *
from common.wasm import *
import lang_loop.loop_tychecker as var_tychecker
from common.compilerSupport import *
# import common.utils as utils
from common.compilerSupport import *


def compileModule(m: mod, cfg: CompilerConfig) -> WasmModule:
    vars = var_tychecker.tycheckModule(m)
    instrs = compileStmts(m.stmts)
    idMain = WasmId('$main')
    locals : list[tuple[WasmId, WasmValtype]] = [(identToWasmId(x), 'i64' if type(xty)==Int else 'i32') for x, xty in vars.types()]

    return WasmModule(imports=wasmImports(cfg.maxMemSize),
                      exports=[WasmExport("main", WasmExportFunc(idMain))],
                      globals=[],
                      data=[],
                      funcTable=WasmFuncTable([]),
                      funcs=[WasmFunc(idMain, [], None, locals, instrs)])

def compileStmts(stmts: list[stmt]) -> list[WasmInstr]:
    instrs : list[WasmInstr]= []
    for stmt in stmts:
        match stmt:
            case StmtExp(e):
                instrs += compileExp(e)
            case Assign(x, e):
                instrs += compileExp(e) + [WasmInstrVarLocal(op='set', id=WasmId(id=f'${x.name}'))]
            case IfStmt(cond, tb, eb):
                instrs += compileExp(cond) + [WasmInstrIf(resultType=None, thenInstrs=compileStmts(tb), elseInstrs=compileStmts(eb))]
            case WhileStmt(cond, b):
                instrs += compileWhile(cond, b)
    return instrs

def compileExp(exp: exp) -> list[WasmInstr]:
    match exp:
        case IntConst(n):
            return [WasmInstrConst(ty='i64', val=n)]
        case BoolConst(n):
            return [WasmInstrConst(ty='i32', val=1 if n else 0)]
        case Name(x):
            return [WasmInstrVarLocal(op='get', id=WasmId(id=f'${x.name}'))]
        case Call(x, args):
            a = [instr for arg in args for instr in compileExp(arg)]
            if x.name == 'print':
                if isinstance(typeOfExp(args[0]), Bool):
                    return a + [WasmInstrCall(id=WasmId('$print_i32'))]
                else:
                    return a + [WasmInstrCall(id=WasmId('$print_i64'))]
            elif x.name == 'input_int':
                return a + [WasmInstrCall(id=WasmId('$input_i64'))]
            else:
                return a + [WasmInstrCall(id=WasmId(f'${x.name}'))]
        case UnOp(op, arg):
            arg_instrs = compileExp(arg)
            match op:
                case USub():
                    return [WasmInstrConst(ty='i64', val=0)] + arg_instrs + [WasmInstrNumBinOp(ty='i64', op='sub')]
                case Not():
                    return arg_instrs + [WasmInstrConst(ty='i32', val=0), WasmInstrIntRelOp(ty='i32', op='eq')]
        case BinOp(left, op, right):
            left_instrs = compileExp(left)
            right_instrs = compileExp(right)
            match op:
                case Add():
                    return left_instrs + right_instrs + [WasmInstrNumBinOp(ty='i64', op='add')]
                case Sub():
                    return left_instrs + right_instrs + [WasmInstrNumBinOp(ty='i64', op='sub')]
                case Mul():
                    return left_instrs + right_instrs + [WasmInstrNumBinOp(ty='i64', op='mul')]
                case Less():
                    return left_instrs + right_instrs + [WasmInstrIntRelOp(ty='i64', op='lt_s')]
                case LessEq():
                    return left_instrs + right_instrs + [WasmInstrIntRelOp(ty='i64', op='le_s')]
                case Greater():
                    return left_instrs + right_instrs + [WasmInstrIntRelOp(ty='i64', op='gt_s')]
                case GreaterEq():
                    return left_instrs + right_instrs + [WasmInstrIntRelOp(ty='i64', op='ge_s')]
                case Eq():
                    instr_type = 'i32' if typeOfExp(left) == Bool() else 'i64'
                    return left_instrs + right_instrs + [WasmInstrIntRelOp(ty=instr_type, op='eq')]
                case NotEq():
                    instr_type = 'i32' if typeOfExp(left) == Bool() else 'i64'
                    return left_instrs + right_instrs + [WasmInstrIntRelOp(ty=instr_type, op='ne')]
                case And():
                    return left_instrs + [WasmInstrIf(resultType='i32', thenInstrs=right_instrs, elseInstrs=[WasmInstrConst(ty='i32', val=0)])]
                case Or():
                    return left_instrs + [WasmInstrIf(resultType='i32', thenInstrs=[WasmInstrConst(ty='i32', val=1)], elseInstrs=right_instrs)]
    raise ValueError(f'Unsupported expression type: {exp}')

def compileWhile(cond: exp, body: list[stmt]) -> list[WasmInstr]:
    start_label = WasmId('$loop_start')
    end_label = WasmId('$loop_end')

    cond_instrs = compileExp(cond)
    body_instrs = compileStmts(body)

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

def identToWasmId(id: Ident) -> WasmId:
    return WasmId(id=f'${id.name}')

def typeOfExp(e: exp) -> ty:
    if e.ty is None or isinstance(e.ty, Void):
        raise ValueError(f'Invalid type for expression: {e}')
    return e.ty.ty