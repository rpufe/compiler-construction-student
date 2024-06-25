from lang_loop.loop_ast import (stmt, mod, StmtExp,
                                Assign, Call, exp,
                                IntConst, Name, UnOp,
                                BinOp, binaryop, Add,
                                Sub, Mul, USub, 
                                ty, IfStmt, WhileStmt, 
                                Int, Not, BoolConst, 
                                NotVoid, Less, LessEq, 
                                Greater, GreaterEq, NotEq,
                                Eq, And, Or)

from common.wasm import (WasmInstr, WasmModule, WasmFuncTable,
                         WasmInstrConst, WasmFunc, WasmId, 
                         WasmInstrCall, WasmExport, WasmExportFunc, 
                         WasmInstrVarLocal, WasmInstrNumBinOp, WasmValtype,
                         WasmInstrIntRelOp, WasmInstrIf, WasmInstrLoop, WasmInstrBlock, WasmInstrBranch)

import lang_loop.loop_tychecker as loop_tychecker
from common.compilerSupport import wasmImports, CompilerConfig

def compileModule(m: mod, cfg: CompilerConfig) -> WasmModule:
    """
    Function to compile the lang_var module
    """

    # Type Check module
    vars = loop_tychecker.tycheckModule(m)
    var_list = list(vars.items())
    # Initialze instruction list
    locals: list[tuple[WasmId, WasmValtype]] = []

    # Define local variables
    for var, info in var_list:
        var_type = "i64" if isinstance(info.ty, Int) else "i32" 
        locals.append((WasmId(f"${var.name}"), var_type))

    # Compile module statements
    wasm_instr: list[WasmInstr] = compileStmts(m.stmts)

    # Create main function
    main = WasmFunc(
        id=WasmId("$main"), params=[], result=None, locals=locals, instrs=wasm_instr
    )
    
    # Create compiled module
    compiled_module = WasmModule(
        imports=wasmImports(1),
        exports=[WasmExport("main", WasmExportFunc(WasmId("$main")))],
        globals=[],
        data=[],
        funcTable=WasmFuncTable([]),
        funcs=[main],
    )

    return compiled_module


def compileStmts(stmts: list[stmt]) -> list[WasmInstr]:
    """
    Function to compile statements
    """

    wasm_instr: list[WasmInstr] = []

    for stmt in stmts:
        match stmt:
            case StmtExp(exp):
                comp_exp = compileExp(exp)
                wasm_instr.extend(comp_exp)
                
            case Assign(var, exp):
                wasm_instr.extend(compileExp(exp))
                wasm_instr.append(WasmInstrVarLocal("set", WasmId(f"${var.name}")))
                
            case IfStmt(cond, if_stmt, else_stmt):
                wasm_instr.extend(compileExp(cond))
                wasm_instr.append(WasmInstrIf(None, compileStmts(if_stmt), compileStmts(else_stmt)))
            
            case WhileStmt(cond, body):
                loop_body = compileLoopBody(cond, body)
                loop: list[WasmInstr] = [WasmInstrLoop(WasmId("$loop_0_start"), loop_body)]
                wasm_instr.append(WasmInstrBlock(WasmId("$loop_0_exit"), None, loop))

    return wasm_instr


def compileExp(exp: exp) -> list[WasmInstr]:
    """
    Function to compile expressions
    """

    wasm_instr: list[WasmInstr] = []
    match exp:
        case IntConst(v):
            wasm_instr.append(WasmInstrConst("i64", v))
            
        case Name(name):
            wasm_instr.append(WasmInstrVarLocal("get", WasmId(f"${name.name}")))
            
        case Call():
            wasm_instr.extend(compileCall(exp))
                
        case UnOp(op, arg):
            match op:
                case USub():
                    # subtract from zero
                    comp_arg = compileExp(arg)
                    wasm_instr.append(WasmInstrConst("i64", 0))
                    wasm_instr.extend(comp_arg)
                    wasm_instr.append(WasmInstrNumBinOp("i64", "sub"))
                case Not():
                    # compare to zero
                    comp_arg = compileExp(arg)
                    wasm_instr.append(WasmInstrConst("i32", 0))
                    wasm_instr.extend(comp_arg)
                    wasm_instr.append(WasmInstrIntRelOp("i32", "eq"))
                    
        case BinOp(left, op, right):
            left_exp = compileExp(left)
            right_exp = compileExp(right)
            wasm_instr.extend(compileBinOp(op, tyOfExp(left), left_exp, right_exp))
        
        case BoolConst(v):
            wasm_instr.append(WasmInstrConst("i32", int(v)))
            
    return wasm_instr
 

def compileBinOp(op: binaryop, ty: ty, left_exp: list[WasmInstr], right_exp: list[WasmInstr]) -> list[WasmInstr]:
    """
    Function to compile Binary Operator
    """
    result_type = "i64" if isinstance(ty, Int) else "i32"
    instr_list: list[WasmInstr] = []
    instr_list.extend(left_exp)
    match op:
        case Add():
            instr_list.extend(right_exp)
            instr_list.append(WasmInstrNumBinOp(result_type, "add"))
        case Sub():
            instr_list.extend(right_exp)
            instr_list.append(WasmInstrNumBinOp(result_type, "sub"))
        case Mul():
            instr_list.extend(right_exp)
            instr_list.append(WasmInstrNumBinOp(result_type, "mul"))
        case Less():
            instr_list.extend(right_exp)
            instr_list.append(WasmInstrIntRelOp(result_type, "lt_s"))
        case Greater():
            instr_list.extend(right_exp)
            instr_list.append(WasmInstrIntRelOp(result_type, "gt_s"))
        case LessEq():
            instr_list.extend(right_exp)
            instr_list.append(WasmInstrIntRelOp(result_type, "le_s"))
        case GreaterEq():
            instr_list.extend(right_exp)
            instr_list.append(WasmInstrIntRelOp(result_type, "ge_s"))
        case Eq():
            instr_list.extend(right_exp)
            instr_list.append(WasmInstrIntRelOp(result_type, "eq"))
        case NotEq():
            instr_list.extend(right_exp)
            instr_list.append(WasmInstrIntRelOp(result_type, "ne"))
        case And():
            instr_list.append(WasmInstrIf("i32", right_exp, [WasmInstrConst("i32", 0)]))
        case Or():
            instr_list.append(WasmInstrIf("i32", [WasmInstrConst("i32", 1)], right_exp))
            
    return instr_list
        
def tyOfExp(e: exp) -> ty:
    """
    Function to return the type of an expression
    """
    match e.ty:
        case NotVoid():
            return e.ty.ty
        case _:
            raise AttributeError(f"Type of expression {e} should be NotVoid() but is {e.ty}")
        
def compileCall(exp: Call) -> list[WasmInstr]:
    """
    Function to compile a call
    """
    instr: list[WasmInstr] = []
    for arg in exp.args:
                instr.extend(compileExp(arg))
    if exp.name.name == "print":
        # check if print must be int or bool
        print_type = "i64" if isinstance(tyOfExp(exp.args[0]), Int) else "i32"
        instr.append(WasmInstrCall(WasmId(f"$print_{print_type}")))
    else:
        instr.append(WasmInstrCall(WasmId("$input_i64")))
        
    return instr

def compileLoopBody(cond: exp, body: list[stmt]) -> list[WasmInstr]:
    """
    Function to compile loop body
    """
    body_instr: list[WasmInstr] = []
    body_instr.extend(compileExp(cond))
    body_instr.append(WasmInstrIf(None, [], [WasmInstrBranch(WasmId("$loop_0_exit"), False)]))
    body_instr.extend(compileStmts(body))
    body_instr.append(WasmInstrBranch(WasmId("$loop_0_start"), False))
    return body_instr