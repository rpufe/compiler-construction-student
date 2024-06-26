from assembly.common import *
import assembly.tac_ast as tac
import common.log as log
from common.prioQueue import PrioQueue

def chooseColor(x: tac.ident, forbidden: dict[tac.ident, set[int]], maxRegs: int) -> int:
    """
    Returns the lowest possible color for variable x that is not forbidden for x.
    """
    forbidden_colors = forbidden.get(x, set())
    for color in range(maxRegs):
        if color not in forbidden_colors:
            return color
    return maxRegs

def colorInterfGraph(g: InterfGraph, secondaryOrder: dict[tac.ident, int]={},
                     maxRegs: int=MAX_REGISTERS) -> RegisterMap:
    """
    Given an interference graph, computes a register map mapping a TAC variable
    to a TACspill variable. Implements the graph coloring algorithm with spilling.

    - Parameter maxRegs is the maximum number of registers we are allowed to use.
    - Parameter secondaryOrder is used by the tests to get deterministic results even
      if two variables have the same number of forbidden colors.
    """
    log.debug(f"Coloring interference graph with maxRegs={maxRegs}")
    colors: dict[tac.ident, int] = {}
    forbidden: dict[tac.ident, set[int]] = {}
    q = PrioQueue(secondaryOrder)

    spillStack: list[tac.ident] = []

    # print()

    for v in g.vertices:
        degree = len(g.succs(v))
        q.push(v, degree)
    
    while not q.isEmpty():
        x = q.pop()
        forbidden[x] = set()

        # print(f'X: {x}')
        for neighbor in g.succs(x):
            # print(f'Neighbor: {neighbor}')
            # print(f'Colors 0: {colors}')
            if neighbor in colors:
                forbidden[x].add(colors[neighbor])

        chosen_color = chooseColor(x, forbidden, maxRegs)
        
        if chosen_color >= maxRegs:
            spillStack.append(x)
        else:
            colors[x] = chosen_color

    
    # print(f'SpillStack: {spillStack}')
    # print(f'Forbidden: {forbidden}')
    # print(f'Colors 1: {colors}')

    spillOffset = maxRegs
    for x in spillStack:
        colors[x] = spillOffset
        spillOffset += 1

    # print(f'Colors 2: {colors}')

    m = RegisterAllocMap(colors, maxRegs)
    return m
