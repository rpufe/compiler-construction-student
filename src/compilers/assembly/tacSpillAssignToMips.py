import assembly.tac_ast as tac
import assembly.tacSpill_ast as tacSpill
import assembly.mips_ast as mips
from typing import *
from assembly.common import *
import assembly.tacInterp as tacInterp
from assembly.mipsHelper import *
from common.compilerSupport import *

def assignToMips(i: tacSpill.Assign) -> list[mips.instr]:
    if isinstance(i.left, tacSpill.Const):
        if isinstance(i.var, tac.Ident):
            return [mips.LoadI(reg(i.var), imm(i.left.value))]
        elif isinstance(i.var, tacSpill.Spill):
            return [mips.LoadI(reg(i.var), imm(i.left.value))]
        else:
            raise ValueError(f'Invalid destination operand in assignment: {i}')
    elif isinstance(i.left, tacSpill.Name):
        if isinstance(i.var, tac.Ident):
            return [mips.Move(reg(i.var), reg(i.left.var.name.name))]
        elif isinstance(i.var, tacSpill.Spill):
            return [mips.Move(reg(i.var), reg(i.left.var.name))]
        else:
            raise ValueError(f'Invalid destination operand in assignment: {i}')
    elif isinstance(i.left, tacSpill.Prim):
        if isinstance(i.left.p, tacSpill.Const):
            if isinstance(i.var, tac.Ident):
                return [mips.LoadI(reg(i.var), imm(i.left.p.value))]
            elif isinstance(i.var, tacSpill.Spill):
                return [mips.LoadI(reg(i.var), imm(i.left.p.value))]
            else:
                raise ValueError(f'Invalid destination operand in assignment: {i}')
        elif isinstance(i.left.p, tacSpill.Name):
            if isinstance(i.var, tac.Ident):
                return [mips.Move(reg(i.var), reg(i.left.p.var.name.name))]
            elif isinstance(i.var, tacSpill.Spill):
                return [mips.Move(reg(i.var), reg(i.left.p.var.name))]
            else:
                raise ValueError(f'Invalid destination operand in assignment: {i}')
        else:
            raise ValueError(f'Unhandled primitive type in assignment: {i.left}')
    elif isinstance(i.left, tacSpill.BinOp):
        if isinstance(i.var, tac.Ident):
            left_reg = reg(i.left.left.p.var.name.name)
            right_reg = reg(i.left.right.p.var.name.name)
            target_reg = reg(i.var.name)
            op = None
            if isinstance(i.left.op, tac.Less):
                op = mips.Less(target_reg, left_reg, right_reg)
            elif isinstance(i.left.op, tac.Add):
                op = mips.Add(target_reg, left_reg, right_reg)
            # Handle other binary operations similarly
            else:
                raise ValueError(f'Unhandled binary operation: {i.left.op}')
            return [mips.Move(target_reg, left_reg), op]
        elif isinstance(i.var, tacSpill.Spill):
            left_reg = reg(i.left.left.p.var.name.name)
            right_reg = reg(i.left.right.p.var.name.name)
            target_reg = reg(i.var.origName)
            op = None
            if isinstance(i.left.op, tac.Less):
                op = mips.Less(target_reg, left_reg, right_reg)
            elif isinstance(i.left.op, tac.Add):
                op = mips.Add(target_reg, left_reg, right_reg)
            # Handle other binary operations similarly
            else:
                raise ValueError(f'Unhandled binary operation: {i.left.op}')
            return [mips.Move(target_reg, left_reg), op]
        else:
            raise ValueError(f'Invalid destination operand in assignment: {i}')
    else:
        raise ValueError(f'Unhandled assignment case: {i}')
