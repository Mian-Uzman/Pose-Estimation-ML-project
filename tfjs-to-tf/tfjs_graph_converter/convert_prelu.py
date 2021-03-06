# SPDX-License-Identifier: MIT
# Copyright © 2020 Patrick Levin
"""Functions to rewrite Prelu-activations as native TensorFlow operations"""

import tfjs_graph_converter.graph_rewrite_util as util
from tfjs_graph_converter.graph_rewrite_util import generate_name_from


def _split_fused_op(node: util.NodeDef,
                    input_node_map: util.NameToNode, _) -> util.NodeList:
    # Possible fused Conv2D patterns are:
    # • Conv2D + BiasAdd
    # • Conv2D + BiasAdd + <Activation>
    # • Conv2D + FusedBatchNorm + <Activation>
    # • Conv2D + Squeeze + BiasAdd
    #
    # Fused MatMul only has one pattern:
    # • MatMul + BiasAdd + <Activation>
    #
    # FusedBatchNorm and Squeeze are not relevant for inference and thus never
    # present in (optimised) frozen graphs generated by tfjs converter.
    # This leaves us with Conv2D|MatMul + BiasAdd + <Activation> as the only
    # remaining possible variants, since Conv2D + BiasAdd doesn't need to be
    # split.
    #
    # We return [Conv2D|MatMul, BiasAdd|BiasAddV1, <Activation>].
    # Unsupported <Activation>-nodes will be dealt with in a separate step
    fused_op_name = node.op[6:]     # remove the '_Fused'-prefix
    fused_ops = list(s.decode('utf-8') for s in node.attr['fused_ops'].list.s)
    inputs = list(node.input)
    names_used = set()

    def node_name(node_index):
        name = generate_name_from(inputs[node_index], input_node_map)
        if name in names_used:
            name = generate_name_from(name, input_node_map,
                                      suffix=fused_ops[node_index-2])
        names_used.add(name)
        return name

    fused_op = util.make_op_node(fused_op_name, inputs[0:2], node_name(1))
    fused_op = util.copy_op_attrs(source=node, target=fused_op)
    bias_add = util.make_op_node(fused_ops[0], [fused_op, inputs[2]],
                                 node_name(2))
    bias_add = util.copy_op_attrs(source=node, target=bias_add)
    activation = util.make_op_node(fused_ops[1], [bias_add] + inputs[3:],
                                   node_name(3))
    return [fused_op, bias_add, activation]


def _split_prelu(node: util.NodeDef,
                 input_node_map: util.NameToNode,
                 weight_modifiers: util.WeightModifiers) -> util.NodeList:
    # Prelu activation is not supported by TF so this functions generates an
    # equivalent formulation:
    # f(x) = alpha*relu(x) if x < 0, relu(x) if x >= 0
    #      = pos(x)+neg(x), where pos(x)=relu(x), and neg(x)=-alpha*relu(-x)
    #
    # We return the sub-graph
    # [pos=Relu(x), Neg(x), Relu(-x), neg=Mul(-alpha, -x), Add(pos, neg)]
    inputs = list(node.input)

    def _get_name(suffix):
        return generate_name_from(node.name, input_node_map, suffix=suffix)

    # here we need to manually keep node names unique in the sub-graph
    # since we cannot modify input_node_map, because we don't have a node yet
    pos = util.make_op_node('Relu', inputs[0], _get_name('Relu'))
    neg_x = util.make_op_node('Neg', inputs[0], _get_name('Neg'))
    neg_relu = util.make_op_node('Relu', neg_x, _get_name('Relu_1'))
    neg_alpha = inputs[1]
    neg = util.make_op_node('Mul', [neg_alpha, neg_relu], _get_name('Mul'))
    add = util.make_op_node('Add', [pos, neg], _get_name('Add'))
    # convert alpha to -alpha by registering a weight modifier function
    weight_modifiers[neg_alpha] = lambda tensor: -tensor
    return [pos, neg_x, neg_relu, neg, add]


def split_fused_prelu(input_graph_def: util.GraphDef) -> util.GraphDef:
    """
    This function looks for fused operations that include a 'Prelu'-activation.
    Matching nodes will be split into individual operations.

    TFJS uses fused operations for performance.
    Some fused activations aren't supported by TF (e.g. 'Prelu'), so we need
    to split the fused ops back into individual ops and replace unsupported
    functions by equivalent supported constructs later.

    Args:
        input_graph_def: TF graph definition to examine

    Returns:
        Updated copy of the input graph with matching nodes replaced by
        individual operations
    """
    def _predicate(node):
        return (util.is_fused_conv2d(node, b'Prelu')
                or util.is_fused_matmul(node, b'Prelu'))
    return util.replace_matching_nodes(input_graph_def, _predicate,
                                       _split_fused_op)


def replace_prelu(input_graph_def: util.GraphDef) -> util.GraphDef:
    """
    Replace all Prelu-activations in the graph with supported TF-operations.

    Args:
        input_graph_def: TF graph definition to examine

    Returns:
        Updated copy of the input graph with Prelu-nodes replaced by supported
        TF operations
    """
    def _predicate(node): return node.op == 'Prelu'
    return util.replace_matching_nodes(input_graph_def, _predicate,
                                       _split_prelu)
