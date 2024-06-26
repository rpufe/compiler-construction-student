# import assembly.tac_ast as tac
import assembly.tacSpill_ast as tacSpill
import assembly.mips_ast as mips
from typing import *
from assembly.common import *
# import assembly.tacInterp as tacInterp
from assembly.mipsHelper import *
from common.compilerSupport import *

def assignToMips(i: tacSpill.Assign) -> list[mips.instr]:
    def prim_to_mips(prim: tacSpill.prim, target_reg: mips.reg) -> List[mips.instr]:
        match prim:
            case tacSpill.Const(value):
                return [mips.LoadI(target_reg, imm(value))]
            case tacSpill.Name(var):
                return [mips.Move(target_reg, reg(var))]

    def binop_to_mips(binop: tacSpill.BinOp) -> List[mips.instr]:
        left_reg = Regs.v0
        right_reg = Regs.a0
        instrs = prim_to_mips(binop.left, left_reg)
        
        match binop.right:
            case tacSpill.Const(value):
                if binop.op.name == 'ADD':
                    instrs += [mips.OpI(opI=binop_opI(binop.op), target=reg(i.var), left=left_reg, right=imm(value))]
                else:
                    instrs += [mips.LoadI(right_reg, imm(value))]
                    instrs += [mips.Op(op=binop_op(binop.op), target=reg(i.var), left=left_reg, right=right_reg)]
            case tacSpill.Name():
                instrs += prim_to_mips(binop.right, right_reg)
                instrs += [mips.Op(op=binop_op(binop.op), target=reg(i.var), left=left_reg, right=right_reg)]
        
        return instrs

    def binop_op(op: tacSpill.Op) -> mips.op:
        match op.name:
            case 'ADD':
                return mips.Add()
            case 'SUB':
                return mips.Sub()
            case 'MUL':
                return mips.Mul()
            # case '<':
            #     return mips.Less()
            # case '<=':
            #     return mips.LessEq()
            # case '>':
            #     return mips.Greater()
            # case '>=':
            #     return mips.GreaterEq()
            # case '==':
            #     return mips.Eq()
            # case '!=':
            #     return mips.NotEq()
            case _:
                raise ValueError(f"Value Error: {op.name}")
            
    def binop_opI(op: tacSpill.Op) -> mips.opI:
        match op.name:
            case 'ADD':
                return mips.AddI()
            # case '<':
            #     return mips.LessI()
            case _:
                raise ValueError(f"Value Error: {op.name}")

    match i.left:
        case tacSpill.Prim(p):
            return prim_to_mips(p, reg(i.var))
        case tacSpill.BinOp(left, op, right):
            return binop_to_mips(tacSpill.BinOp(left, op, right))
