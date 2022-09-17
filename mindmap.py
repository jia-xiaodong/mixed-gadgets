#!/usr/bin/python
# -*- coding: utf-8 -*-

from PIL import Image, ImageFilter, ImageTk
import tkinter as tk
from tkinter import filedialog
from tkinter import messagebox
from tkinter import ttk
from enum import Enum


class EdgeDir:
    SINGLE = 0
    MUTUAL = 1


class Edge:
    """
    图的边
    """
    def __init__(self, index: int, node1: int, node2: int, direction: EdgeDir, text: str):
        self._index = index
        self._n1 = node1
        self._n2 = node2
        self._dir = direction
        self._txt = text

    @property
    def index(self):
        return self._index

    @property
    def direction(self):
        return self._dir

    @property
    def n1(self):
        """
        start node if it's directional
        """
        return self._n1

    @property
    def n2(self):
        """
        end node if it's directional
        """
        return self._n2

    @property
    def text(self):
        return self._txt

    def ny(self, nx):
        """
        @return 返回另一个节点
        """
        return self._n1 if self._n2 == nx else self._n2


class Node:
    """
    图的节点
    """
    def __init__(self, index: int, text: str):
        self._index = index
        self._text = text
        self._edges_out = []  # 出边
        self._edges_in = []   # 入边

    @property
    def index(self):
        return self._index

    @property
    def edges_out(self):
        """
        该节点的所有出边
        """
        return self._edges_out

    @property
    def edges_in(self):
        """
        该节点的所有出边
        """
        return self._edges_in

    @property
    def edges(self):
        """
        该节点的所有边
        """
        return self._edges_in + self._edges_out


class Graph:
    """
    图的拓扑信息
    """
    def __init__(self):
        self._nodes = {}
        self._edges = {}

    def add_node(self, node: Node):
        """
        添加新节点到图里。
        因为是新节点，所以不应包含“edge”信息
        """
        if node.index not in self._nodes:
            self._nodes[node.index] = node

    def remove_node(self, node_index: int):
        if node_index not in self._nodes:
            return
        target_node: Node = self._nodes.pop(node_index)
        # 更新相邻节点的邻接表
        nodes1, edges1 = self.get_outgoing(target_node)
        for node in nodes1:  # 更新相邻节点的入边表
            node.edges_in.remove(node_index)
        # 更新相邻节点的邻接表
        nodes2, edges2 = self.get_incoming(target_node)
        for node in nodes2:  # 更新相邻节点的出边表
            node.edges_out.remove(node_index)
        # 所有相关的“边”也要删掉
        for e in edges1 + edges2:
            self._edges.pop(e)

    def add_edge(self, edge: Edge):
        """
        给图中的两个节点，搭建一条边
        """
        if edge.index in self._edges:   # 边已存在
            return
        if edge.n1 not in self._nodes:  # 节点不存在
            return
        if edge.n2 not in self._nodes:  # 节点不存在
            return
        self._edges[edge.index] = edge
        # 更新两个节点的邻接表
        n1: Node = self._nodes[edge.n1]
        n2: Node = self._nodes[edge.n2]
        if edge.direction is EdgeDir.SINGLE:  # n1 --> n2
            n1.edges_out.append(edge.index)
            n2.edges_in.append(edge.index)
        else:  # n1 <--> n2
            n1.edges_in.append(edge.index)
            n1.edges_out.append(edge.index)
            n2.edges_in.append(edge.index)
            n2.edges_out.append(edge.index)

    def remove_edge(self, edge: Edge):
        if edge.index not in self._edges:
            return
        n1: Node = self._nodes[edge.n1]
        n2: Node = self._nodes[edge.n2]
        if edge.direction == EdgeDir.SINGLE:  # n1 --> n2
            n1.edges_out.remove(edge.index)
            n2.edges_in.remove(edge.index)
        else:  # n1 <--> n2
            n1.edges_in.remove(edge.index)
            n1.edges_out.remove(edge.index)
            n2.edges_in.remove(edge.index)
            n2.edges_out.remove(edge.index)

    def free_index(self):
        pass

    def get_edge(self, n1: Node, n2: Node):
        """
        在图中搜索一条边，连接指定的两个节点
        """
        for edge_index in n1.edges:
            edge = self._edges[edge_index]
            if edge.direction == EdgeDir.MUTUAL:
                if edge.n1 == n2.index or edge.n2 == n2.index:
                    return edge
            elif edge.n2 == n2.index:
                return edge
        return None

    def get_outgoing(self, n: Node):
        """
        与给定节点相连的所有节点，给定节点作为出发节点
        @return 所有相连节点的索引
        """
        edges = [self._edges[e] for e in n.edges_out]
        nodes = [self._nodes[e.ny(n.index)] for e in edges]
        return nodes, edges

    def get_incoming(self, n: Node):
        """
        与给节点相连的所有节点，给定节点作为终点节点
        @return 所有相连节点的索引
        """
        edges = [self._edges[e] for e in n.edges_in]
        nodes = [self._nodes[e.ny(n.index)] for e in edges]
        return nodes, edges


class CanvasShape:
    """
    MVC设计模式中的Controller。
    既保存了View方面的数据，也保存了Model方面的数据
    """
    def __init__(self, canvas: tk.Canvas):
        self._cvs = canvas
        self._vid = -1  # view id
        self._mid = -1  # model id
        self._dat = None

    @property
    def vid(self):
        return self._vid

    @vid.setter
    def vid(self, value):
        self._vid = value

    @property
    def mid(self):
        return self._mid

    @mid.setter
    def mid(self, value):
        self._mid = value

    @property
    def data(self):
        return self._dat

    @data.setter
    def data(self, value):
        self._dat = value

    def draw(self):
        pass


class Link(CanvasShape):
    def __init__(self, canvas: tk.Canvas):
        CanvasShape.__init__(self, canvas)
        self._pos0 = (0, 0)  # 起点
        self._pos1 = (0, 0)  # 终点
        self._type = EdgeDir.MUTUAL

    @property
    def center(self):
        return (self._pos0[0] + self._pos1[0]) / 2, (self._pos0[1] + self._pos1[1]) / 2

    @property
    def pos0(self):
        return self._pos0

    @pos0.setter
    def pos0(self, value):
        self._pos0 = value

    @property
    def pos1(self):
        return self._pos1

    @pos1.setter
    def pos1(self, value):
        self._pos1 = value

    @property
    def type(self):
        return self._type

    @type.setter
    def type(self, value: EdgeDir):
        self._type = value


class Rect(CanvasShape):
    def __init__(self, canvas: tk.Canvas):
        CanvasShape.__init__(self, canvas)
        self._top_left = (0, 0)
        self._bottom_right = (0, 0)

    @property
    def width(self):
        return self._bottom_right[0] - self._top_left[0]

    @property
    def height(self):
        return self._bottom_right[1] - self._top_left[1]

    @property
    def center(self):
        return (self._bottom_right[0] + self._top_left[0]) / 2, (self._bottom_right[1] + self._top_left[1]) / 2


class Oval(CanvasShape):
    def __init__(self, canvas: tk.Canvas):
        CanvasShape.__init__(self, canvas)
        self._top_left = (0, 0)
        self._bottom_right = (0, 0)

    @property
    def top_left(self):
        return self._top_left

    @top_left.setter
    def top_left(self, value):
        self._top_left = value

    @property
    def bottom_right(self):
        return self._bottom_right

    @bottom_right.setter
    def bottom_right(self, value):
        self._bottom_right = value

    def draw(self):
        x0, y0 = self._top_left
        x1, y1 = self._bottom_right
        self._vid = self._cvs.create_oval(x0, y0, x1, y1)


class MindMapCanvas(tk.Canvas):
    def __init__(self, master, *args, **kwargs):
        tk.Canvas.__init__(self, master, *args, **kwargs)
        self._graph = Graph()
        self._shapes = []
        self.bind('<Configure>', self.auto_resize)

    def serialize(self):
        pass

    def deserialize(self):
        pass

    def create_root_node(self):
        pass

    def auto_resize(self, evt):
        if len(self._shapes) == 0:
            first = Oval(self)
            w = self.winfo_width()
            h = self.winfo_height()
            half = min(w, h) / 4
            first.top_left = (w/2-half, h/2-half)
            first.bottom_right = (w/2+half, h/2+half)
            first.draw()
            self._shapes.append(first)


if __name__ == "__main__":
    root = tk.Tk(className=' Mind Map')  # extra blank to fix lowercase caption
    MindMapCanvas(root).pack(fill=tk.BOTH, expand=tk.YES)
    root.mainloop()
