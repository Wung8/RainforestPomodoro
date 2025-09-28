from os import environ
environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
from win32gui import SetWindowPos

import numpy as np
import cv2
import pygame
import math, random
from attrdict import AttrDict
import ctypes
import pygetwindow as gw
import win32gui


pygame.init()

surface_size = 1920, 1200
screen_size = 1920, 1200

foreground_surface = pygame.Surface(surface_size, pygame.SRCALPHA)
background_surface = pygame.Surface(surface_size)
surfaces = [pygame.Surface(surface_size, pygame.SRCALPHA) for i in range(4)]
growing_surfaces = [pygame.Surface(surface_size, pygame.SRCALPHA) for i in range(4)]
screen = pygame.display.set_mode(screen_size)
clock = pygame.time.Clock()

pygame.display.set_caption("My Pygame Window")

bg = (100, 100, 140)
fade = (20, 60, 30)
brown = (190, 140, 100)
green = (145, 180, 90)
dark_green = (90, 120, 75)
orange = (220, 150, 100)
foreground_color = (70, 90, 40)   # dark brownish-green
vegetation_color = (75, 100, 45)  # lighter green for small plants

def tint_surface(surface, color=fade, alpha=0.5):
    """
    Apply a weighted average filter between the surface pixels and a given color.
    alpha=0 → keep original, alpha=1 → full color.
    """
    arr = pygame.surfarray.pixels3d(surface)   # shape (w,h,3)
    r, g, b = color
    # blend with broadcasting
    arr[:] = (arr * (1-alpha) + np.array([r,g,b]) * alpha).astype(np.uint8)
    del arr  # unlock surface

class Node():
    def __init__(self, circle, type_, dist, height, angle, parent=None, children=None):
        all_nodes.append(self)
        if children is None: children = []
        self.circle = circle
        self.type_ = type_
        self.dist = dist
        self.height = height
        self.angle = angle
        self.parent = parent
        self.children = children
        self.r = self.circle.r

    @property
    def pos(self):
        return self.circle.pos

    def addChild(self, node):
        self.children.append(node)

    def display(self, color=brown, surface=None):
        if surface is None: surface = surfaces[0]
        for child in self.children:
            c1 = self.circle
            c2 = child.circle
            poly = circleTangents(c1, c2)
            pygame.draw.polygon(surface, color, poly, 0)
        pygame.draw.circle(surface, color, self.circle.pos, self.circle.r)


class Base():
    def __init__(self, pos, r, angle, children=None):
        all_nodes.append(self)
        if children is None: children = []
        self.pos = pos
        self.r = r
        self.R = r
        self.angle = angle
        self.children = children
        self.height = 0

    def addChild(self, node):
        self.children.append(node)

    def display(self, color=brown, surface=None):
        if surface is None: surface = surfaces[0]
        p1, p2 = (self.pos[0]-self.r, self.pos[1]), (self.pos[0]+self.r, self.pos[1])

        for child in self.children:
            p3, p4 = pointToCircleTangents(p1, child.circle)
            p5, p6 = pointToCircleTangents(p2, child.circle)

            pygame.draw.polygon(surface, color, (p1,p3,p4), 0)
            pygame.draw.polygon(surface, color, (p1,p5,p6), 0)
            pygame.draw.polygon(surface, color, (p2,p3,p4), 0)
            pygame.draw.polygon(surface, color, (p2,p5,p6), 0)
            pygame.draw.polygon(surface, color, (p1,p2,p3,p5), 0)
        

def draw_rotated_square_surf(surface, center, size, angle_deg, color):
    # create a temporary surface with per-pixel alpha
    s = int(size)
    tmp = pygame.Surface((s, s), pygame.SRCALPHA)
    # draw square centered in tmp
    pygame.draw.rect(tmp, color, (0,0,s,s))
    # rotate surface (angle in degrees, CCW)
    rotated = pygame.transform.rotate(tmp, angle_deg)
    # get rect and place its center at 'center'
    r = rotated.get_rect(center=center)
    surface.blit(rotated, r)

def scaleVec(v, s):
    return v[0] * s, v[1] * s

class Leaf():
    def __init__(self, parent, pos):
        self.parent = parent
        self.pos = pos

depths = [
    0,
    0,
    0,
    1,
    0,
    0,
    1,
    1,
    0,
    2,
    1,
    0,
    1,
    1,
    2,
    1,
    0,
    0,
    2,
    2,
    1,
    1,
    0,
    3,
    3,
    2,
    0,
    1,
    1,
    1,
    0,
    0,
    0,
    
]

class Tree():
    def __init__(self, name, base, height, leaves, canopy_info, colors):
        if len(trees) > 20: self.depth = random.choice([0,1,1,2,2,3,3,3,3])
        else: self.depth = depths[len(trees)]
        self.surface = growing_surfaces[self.depth]

        trees.append(self)
        trees.sort(key=lambda p: -p.depth)
        
        self.name = name
        self.base = base
        self.height = height
        self.leaves = leaves
        self.canopy_info = canopy_info
        self.colors = colors

        self.growth = 0.02
        self.generate()

    def generate(self):
        self.base.r = self.growth**0.5 * self.base.R
        parseme = self.base.children[:]
        while parseme:
            node = parseme.pop()
            node.circle.pos = addVec(node.parent.pos, scaleVec(node.dist, self.growth*[1,self.growth**(-0.5)][node.type_=="trunk"]))
            node.circle.r = self.growth**0.5 * node.r
            parseme += node.children
            
        
        self.leaves_g = []
        self.leaves2_g = []
        self.leaves3_g = []
        for leaf in self.leaves:
            leaf.pos = leaf.parent.pos
            for i in range(int(self.canopy_info.density * self.growth**0.5)):
                r = random.random() ** 2.9 * self.canopy_info.spread * self.growth
                angle = random.random()*2*math.pi
                pos = addVector(leaf.pos, r, angle, stretch=self.canopy_info.stretch)
                w = (math.sin(angle)+1)/2
                color = weightedAvg(fade, weightedAvg(
                    self.colors.leaf1,
                    self.colors.leaf2,
                    w,
                    1-w,
                ), self.depth*0.333, 1-self.depth*0.333)
            
                self.leaves_g.append((pos, 10, random.random()*360, color))

        self.leaves2 = []
        for l1,l2 in zip(self.leaves, self.leaves[1:]):
            if math.dist(l1.pos,l2.pos) > self.canopy_info.spread*2.5: continue
            self.leaves2 += right_angle_points(l1.pos, l2.pos)

        
        self.leaves3 = [
            addVector(avg([l.pos for l in self.leaves]), -range_([l.pos for l in self.leaves])/2.5-10, math.pi/2),
            avg([l.pos for l in self.leaves[:3]]),
            avg([l.pos for l in self.leaves[-3:]])
        ]

        for leaf in self.leaves2:
            for i in range(int(self.canopy_info.density // 2 * self.growth**0.5)):
                r = random.random() ** 2.9 * self.canopy_info.spread * 0.7 * self.growth
                angle = random.random()*2*math.pi
                pos = addVector(leaf, r, angle, stretch=self.canopy_info.stretch)
                self.leaves2_g.append((pos, 10, random.random()*360, weightedAvg(fade, self.colors.leaf1, self.depth*0.333, 1-self.depth*0.333)))

        for leaf in self.leaves3:
            for i in range(int(self.canopy_info.density * self.growth**0.5)):
                r = random.random() ** 2.9 * self.canopy_info.spread * self.growth
                angle = random.random()*2*math.pi
                pos = addVector(leaf, r, angle, stretch=self.canopy_info.stretch)
                self.leaves3_g.append((pos, 10, random.random()*360, weightedAvg(fade, self.colors.leaf2, self.depth*0.333, 1-self.depth*0.333)))

    def addNode(self, node):
        self.base.addChild(node)

    def display(self):
        if self.growth < 0.8:
            self.growth += 0.03
            self.generate()
        elif self.growth < 1:
            self.growth += 0.01
            self.generate()
        elif self.growth < 2:
            self.surface = surfaces[self.depth]
            self.growth = 99
        else:
            return
            

        for leaf in self.leaves3_g:
            draw_rotated_square_surf(self.surface, *leaf)


        parseme = [self.base]
        while parseme:
            node = parseme.pop()

            if node.height < self.height:
                w = min(1, (1.5*node.height/self.height) ** 0.5)
                
            depth = 0
            node2=node
            while node2.children:
                node2 = node2.children[0]
                depth += 1
                if depth > 3: break
            if depth<=3:
                w=0.5
                
            
            node.display(weightedAvg(fade, weightedAvg(
                self.colors.trunk1,
                self.colors.trunk2,
                w,
                (1-w)
            ), self.depth*0.333, 1-self.depth*0.333), surface=self.surface)
            parseme += node.children

        for leaf in self.leaves_g:
            draw_rotated_square_surf(self.surface, *leaf)

        for leaf in self.leaves2_g:
            draw_rotated_square_surf(self.surface, *leaf)

def addVec(v1,v2):
    return v1[0]+v2[0], v1[1]+v2[1]
            
def weightedAvg(v1, v2, w1, w2):
    return tuple((np.array(v1)*w1 + np.array(v2)*w2) / (w1+w2))


class Circle():
    def __init__(self, pos, r):
        self.pos = pos
        self.r = r

    def info(self):
        return self.pos, self.r

all_nodes = []

def pointToCircleTangents(pos, circle):
    px, py = pos
    cx, cy = circle.pos
    r = circle.r
    dx, dy = px - cx, py - cy
    dist2 = dx*dx + dy*dy
    if dist2 <= r*r:
        return [(circle.pos[0]-circle.r, circle.pos[1]), (circle.pos[0]+circle.r, circle.pos[1])]
        return []  # inside or on circle: no valid tangents
    dist = math.sqrt(dist2)

    a = r*r / dist2
    b = r * math.sqrt(dist2 - r*r) / dist2

    tx1 = cx + a*dx - b*dy
    ty1 = cy + a*dy + b*dx
    tx2 = cx + a*dx + b*dy
    ty2 = cy + a*dy - b*dx

    return [(tx1, ty1), (tx2, ty2)]

def circleTangents(c1, c2):
    (pos1, r1) = c1.info()
    x1, y1 = pos1
    (pos2, r2) = c2.info()
    x2, y2 = pos2
    dx, dy = x2 - x1, y2 - y1
    d2 = dx*dx + dy*dy
    if d2 == 0: 
        return []
    d = math.sqrt(d2)
    # external tangents
    vx, vy = dx/d, dy/d
    res = []
    for sign in (-1, 1):
        c = (r1 - r2) / d
        h = math.sqrt(max(0.0, 1.0 - c*c))
        nx = vx * c - sign * h * vy
        ny = vy * c + sign * h * vx
        # tangent points
        tx1 = x1 + r1 * nx
        ty1 = y1 + r1 * ny
        tx2 = x2 + r2 * nx
        ty2 = y2 + r2 * ny
        res.append(((tx1, ty1), (tx2, ty2)))
    poly = [res[0][0], res[0][1], res[1][1], res[1][0]]
    return poly


def generateTree(
    name,
    base_info,
    trunk_info,
    branch_info,
    canopy_info,
    color_info,
    iteration=8
    ):

    resolution=15
    # generate trunk
    trunk_height = random.randint(trunk_info.min_height, trunk_info.max_height)
    base = Base(base_info.base_pos, base_info.base_width, math.pi/2)
    curr = base
    height = base.r

    trunk_nodes = []

    parseme = [(base,0)]
    while parseme:
        curr, height = parseme.pop()
        if height > trunk_height: continue
        split = random.random() < trunk_info.split_rate
        if not split:
            r = trunk_info.min_width + (base.r - trunk_info.min_width) * (trunk_info.taper_rate + 1/trunk_info.taper)/(trunk_info.taper_rate * height + 1/trunk_info.taper)
            curr_height = trunk_height / resolution * (trunk_info.seg_min_height + (trunk_info.seg_max_height - trunk_info.seg_min_height) * random.random())
            curr_angle = curr.angle+([-1,1][math.cos(curr.angle) > 0] * randomRange(*trunk_info.angle_randomness)) / 180 * math.pi
            pos = (curr.pos[0] + curr_height*math.cos(curr_angle), curr.pos[1] - curr_height*math.sin(curr_angle))
            node = Node(
                Circle(
                    pos,
                    r
                ),
                type_="trunk",
                dist=getVec(curr_height, curr_angle),
                height=height,
                angle=curr_angle,
                parent=curr,
            )
            curr.addChild(node)
            parseme.append((node, height+curr_height))
        else:
            side = -1
            for i in range(2):
                side *= -1
                r = trunk_info.min_width + (base.r - trunk_info.min_width) * (trunk_info.taper_rate + 1/trunk_info.taper)/(trunk_info.taper_rate * height + 1/trunk_info.taper)
                curr_height = trunk_height / resolution * (trunk_info.seg_min_height + (trunk_info.seg_max_height - trunk_info.seg_min_height) * random.random())
                curr_angle = curr.angle + side*randomRange(trunk_info.min_split_angle/2, trunk_info.max_split_angle/2) / 180 * math.pi
                pos = (curr.pos[0] + curr_height*math.cos(curr_angle), curr.pos[1] - curr_height*math.sin(curr_angle))
                node = Node(
                    Circle(
                        pos,
                        r
                    ),
                    type_="trunk",
                    dist=getVec(curr_height, curr_angle),
                    height=height,
                    angle=curr_angle,
                    parent=curr,
                )
                curr.addChild(node)
                parseme.append((node, height+curr_height))
            
        trunk_nodes.append(curr)

    trunk_height2 = trunk_height
    trunk_height = curr.pos[1]

    side = [-1,1][random.random() > 0.5]
    for trunk_node in trunk_nodes:
        if trunk_node.height < trunk_height2*branch_info.branchoff_min_height: continue

        if random.random() < branch_info.branchoff_prob:
            curr_angle = trunk_node.angle + (side * branch_info.branchoff_angle) / 180 * math.pi
            curr_height = branch_info.seg_height * (branch_info.seg_min_height + (branch_info.seg_max_height-branch_info.seg_min_height)*random.random())
            pos = (trunk_node.pos[0] + curr_height*math.cos(curr_angle), trunk_node.pos[1] - curr_height*math.sin(curr_angle))
            r = branch_info.width
            node = Node(
                Circle(
                    pos,
                    r
                ),
                type_="branch",
                dist=getVec(curr_height, curr_angle),
                height=trunk_node.height+curr_height,
                angle=curr_angle,
                parent=trunk_node,
            )
            trunk_node.addChild(node)
            side *= -1

            parseme = [(node, random.randint(branch_info.min_seg, branch_info.max_seg))]

            while parseme:
                curr, seg = parseme.pop()
                if seg == 0: continue
                if trunk_height - curr.pos[1] > branch_info.branch_max_height: continue
                probs = branch_info.branch_probs
                n = random.choices(list(range(len(probs))), weights=probs, k=1)[0]
                if n == 0:
                    curr_angle = curr.angle + randomAngle(branch_info.branchoff_angle_randomness)
                    curr_height = branch_info.seg_height * randomRange(branch_info.seg_min_height, branch_info.seg_max_height)
                    pos = addVector(curr.pos, curr_height, curr_angle)
                    r = branch_info.width
                    node = Node(
                            Circle(
                                pos,
                                r
                            ),
                            type_="branch",
                            dist=getVec(curr_height, curr_angle),
                            height=curr.height+curr_height,
                            angle=curr_angle,
                            parent=curr
                        )
                    curr.addChild(node)
                    parseme.append((node,seg-1))
                else:
                    for i in range(n):
                        if math.cos(curr.angle)+(random.random()-0.5)/1000 < 0: sides = [-1,1]
                        else: sides = [1,-1]
                        side2 = sides[random.random() > branch_info.branch_preference]
                        curr_angle = curr.angle + side2*branch_info.branch_angle/180*math.pi + randomAngle(branch_info.branchoff_angle_randomness)
                        curr_height = branch_info.seg_height * randomRange(branch_info.seg_min_height, branch_info.seg_max_height)
                        pos = addVector(curr.pos, curr_height, curr_angle)
                        r = branch_info.width
                        node = Node(
                                Circle(
                                    pos,
                                    r
                                ),
                                type_="branch",
                                dist=getVec(curr_height, curr_angle),
                                height=curr.height+curr_height,
                                angle=curr_angle,
                                parent=curr
                            )
                        curr.addChild(node)
                        parseme.append((node,seg-1))
                        side2 *= -1
                        
    leaf_nodes = []
    parseme = [base]
    while parseme:
        curr = parseme.pop()
        parseme += curr.children
        if len(curr.children) == 0:
            leaf_nodes.append(curr)

    leaves = []
    n = 0
    for leaf_node in leaf_nodes:
        pos1 = leaf_node.pos
        m = 0
        for leaf_node2 in leaf_nodes[n+1:][::-1]:
            m -= 1
            pos2 = leaf_node2.pos
            if math.dist(pos1, pos2) < canopy_info.min_dist:
                del leaf_nodes[m]
                m += 1
        leaves.append(Leaf(leaf_node, pos1))
        n += 1

    leaves.sort(key=lambda p: p.pos[0])

    if len(leaves) <= 3 or \
       leaves[-1].pos[0]-leaves[0].pos[0] < canopy_info.leaf_spread and iteration != 0:
        return generateTree(name, base_info, trunk_info, branch_info, canopy_info, color_info, iteration-1)

    return Tree(name, base, trunk_height2, leaves, canopy_info, color_info)

def getVec(dist, angle):
    return dist*math.cos(angle), -dist*math.sin(angle)

def avg(p_lst):
    xsum = 0
    ysum = 0
    for p in p_lst:
        xsum += p[0]
        ysum += p[1]
    xsum /= len(p_lst)
    ysum /= len(p_lst)
    return xsum, ysum

def range_(p_lst):
    miny=p_lst[0][1]
    maxy=p_lst[0][1]
    for p in p_lst:
        y=p[1]
        if y<miny:
            miny=y
        if y>maxy:
            maxy=y
    return maxy-miny

def right_angle_points(A, B):
    x1, y1 = A
    x2, y2 = B
    mx, my = (x1 + x2)/2, (y1 + y2)/2  # midpoint
    dx, dy = x2 - x1, y2 - y1
    dist = math.hypot(dx, dy)
    r = dist / 2

    # unit perpendiculars
    ux, uy = -dy/dist, dx/dist

    # two possible C’s
    C1 = (mx + ux * r, my + uy * r)
    C2 = (mx - ux * r, my - uy * r)

    return C1, C2

def randomAngle(angle):
    return (random.random()*2*angle-angle) / 180 * math.pi

def randomRange(min_, max_):
    return min_ + (max_-min_) * random.random()
    
def addVector(pos, dist, angle, stretch=1):
    return (pos[0] + dist*math.cos(angle), pos[1] - dist*math.sin(angle) * stretch)


Kapok_info = AttrDict({
        "name": "Kapok",
        "base_info": AttrDict({
            "base_pos": (600,700), # position of base of tree
            "base_width": 40, # half of width of base of tree
        }),
        "trunk_info": AttrDict({
            "min_height": 500, # min height of trunk
            "max_height": 800, # max height of trunk
            "min_width": 3.5, # min width of trunk
            "angle_randomness": (0,0), # +- randomness to trunk angle
            "taper": 0.05, # taper constant
            "taper_rate": 1, # taper rate
            "seg_min_height": 1, # min height multiplier for trunk segment
            "seg_max_height": 1, # max height multiplier for trunk segment
            "split_rate": 0,
            "min_split_angle": 0,
            "max_split_angle": 0,
        }),
        "branch_info": AttrDict({
            "branch_max_height": 20,
            "branchoff_min_height": 0.8, # minimum height where branches can start
            "branchoff_angle": 60, # angle with respect to parent trunk/branch branches off
            "branchoff_angle_randomness": 0, # +- randomness to branchoff angle
            "branchoff_prob": 0.8, # probability of branch per trunk segment
            "branch_probs": [0, 0.6, 0.4], # probability of branch per branch segment
            "branch_preference": 0.9, # up/down
            "branch_angle": 30,
            "min_seg": 4, # minimum branch segments
            "max_seg": 6, # maximum branch segments
            "width": 2, # width of branch
            "seg_height": 20, # height of segment
            "seg_min_height": 0.5, # min height multiplier for branch segment
            "seg_max_height": 1, # max height multiplier for branch segment
        }),
        "canopy_info": AttrDict({
            "stretch": 1,
            "min_dist": 30,
            "hang_up": False,
            "hang_down": True,
            "density": 200,
            "spread": 25,
            "leaf_spread": 75,
            "bigleaf": False,
        }),
        "color_info": AttrDict({
            "leaf1": green,
            "leaf2": dark_green,
            "leaf3": (130, 160, 90),
            "trunk1": (190, 140, 100),
            "trunk2": (130, 100, 80),
        })
    })

PurpleHeart_info = AttrDict({
        "name": "PurpleHeart",
        "base_info": AttrDict({
            "base_pos": (600,700), # position of base of tree
            "base_width": 25, # half of width of base of tree
        }),
        "trunk_info": AttrDict({
            "min_height": 300, # min height of trunk
            "max_height": 800, # max height of trunk
            "min_width": 2.5, # min width of trunk
            "angle_randomness": (0,0), # +- randomness to trunk angle
            "taper": 0.05, # taper constant
            "taper_rate": 1, # taper rate
            "seg_min_height": 1, # min height multiplier for trunk segment
            "seg_max_height": 1, # max height multiplier for trunk segment
            "split_rate": 0.06,
            "min_split_angle": 20,
            "max_split_angle": 30,
        }),
        "branch_info": AttrDict({
            "branch_max_height": 30,
            "branchoff_min_height": 0.3, # minimum height where branches can start
            "branchoff_angle": 30, # angle with respect to parent trunk/branch branches off
            "branchoff_angle_randomness": 0, # +- randomness to branchoff angle
            "branchoff_prob": 0.4, # probability of branch per trunk segment
            "branch_probs": [0.4, 0.3, 0.3], # probability of branch per branch segment
            "branch_preference": 0.75, # up/down
            "branch_angle": 30,
            "min_seg": 6, # minimum branch segments
            "max_seg": 8, # maximum branch segments
            "width": 2, # width of branch
            "seg_height": 20, # height of segment
            "seg_min_height": 0.5, # min height multiplier for branch segment
            "seg_max_height": 1, # max height multiplier for branch segment
        }),
        "canopy_info": AttrDict({
            "stretch": 0.3,
            "min_dist": 20,
            "hang_up": False,
            "hang_down": True,
            "density": 50,
            "spread": 18,
            "leaf_spread": 75,
            "bigleaf": False,
        }),
        "color_info": AttrDict({
            "leaf1": green,
            "leaf2": dark_green,
            "leaf3": (130, 160, 90),
            "trunk1": (190, 140, 100),
            "trunk2": (130, 100, 80),
        })
    })
BigLeafMahogany_info = AttrDict({
        "name": "BigLeafMahogany",
        "base_info": AttrDict({
            "base_pos": (600,700), # position of base of tree
            "base_width": 15, # half of width of base of tree
        }),
        "trunk_info": AttrDict({
            "min_height": 200, # min height of trunk
            "max_height": 400, # max height of trunk
            "min_width": 3, # min width of trunk
            "angle_randomness": (0,0), # +- randomness to trunk angle
            "taper": 0.05, # taper constant
            "taper_rate": 1, # taper rate
            "seg_min_height": 1, # min height multiplier for trunk segment
            "seg_max_height": 1, # max height multiplier for trunk segment
            "split_rate": 0.06,
            "min_split_angle": 20,
            "max_split_angle": 30,
        }),
        "branch_info": AttrDict({
            "branch_max_height": 20,
            "branchoff_min_height": 0.2, # minimum height where branches can start
            "branchoff_angle": 30, # angle with respect to parent trunk/branch branches off
            "branchoff_angle_randomness": 0, # +- randomness to branchoff angle
            "branchoff_prob": 0.4, # probability of branch per trunk segment
            "branch_probs": [0.3, 0.5, 0.2], # probability of branch per branch segment
            "branch_preference": 0.25, # up/down
            "branch_angle": 30,
            "min_seg": 6, # minimum branch segments
            "max_seg": 8, # maximum branch segments
            "width": 2.5, # width of branch
            "seg_height": 20, # height of segment
            "seg_min_height": 0.5, # min height multiplier for branch segment
            "seg_max_height": 1, # max height multiplier for branch segment
        }),
        "canopy_info": AttrDict({
            "stretch": 0.8,
            "min_dist": 20,
            "hang_up": False,
            "hang_down": True,
            "density": 80,
            "spread": 30,
            "leaf_spread": 75,
            "bigleaf": False,
        }),
        "color_info": AttrDict({
            "leaf1": green,
            "leaf2": dark_green,
            "leaf3": (130, 160, 90),
            "trunk1": (190, 140, 100),
            "trunk2": (130, 100, 80),
        })
    })
Shrub_info = AttrDict({
        "name": "Shrub",
        "base_info": AttrDict({
            "base_pos": (600,700), # position of base of tree
            "base_width": 2, # half of width of base of tree
        }),
        "trunk_info": AttrDict({
            "min_height": 20, # min height of trunk
            "max_height": 30, # max height of trunk
            "min_width": 1, # min width of trunk
            "angle_randomness": (2,4), # +- randomness to trunk angle
            "taper": 0.05, # taper constant
            "taper_rate": 1, # taper rate
            "seg_min_height": 1, # min height multiplier for trunk segment
            "seg_max_height": 1, # max height multiplier for trunk segment
            "split_rate": 0.06,
            "min_split_angle": 20,
            "max_split_angle": 30,
        }),
        "branch_info": AttrDict({
            "branch_max_height": 10,
            "branchoff_min_height": 0.1, # minimum height where branches can start
            "branchoff_angle": 30, # angle with respect to parent trunk/branch branches off
            "branchoff_angle_randomness": 0, # +- randomness to branchoff angle
            "branchoff_prob": 0.4, # probability of branch per trunk segment
            "branch_probs": [0.3, 0.4, 0.4], # probability of branch per branch segment
            "branch_preference": 0.25, # up/down
            "branch_angle": 30,
            "min_seg": 2, # minimum branch segments
            "max_seg": 4, # maximum branch segments
            "width": 1, # width of branch
            "seg_height": 20, # height of segment
            "seg_min_height": 0.5, # min height multiplier for branch segment
            "seg_max_height": 1, # max height multiplier for branch segment
        }),
        "canopy_info": AttrDict({
            "stretch": 0.8,
            "min_dist": 20,
            "hang_up": False,
            "hang_down": True,
            "density": 40,
            "spread": 10,
            "leaf_spread": 30,
            "bigleaf": False,
        }),
        "color_info": AttrDict({
            "leaf1": green,
            "leaf2": dark_green,
            "leaf3": (130, 160, 90),
            "trunk1": (190, 140, 100),
            "trunk2": (130, 100, 80),
        })
    })

def generateRandomTree():
    tree_info = random.choice([Kapok_info, PurpleHeart_info, BigLeafMahogany_info, Shrub_info])
    generateTree(
        name=tree_info.name,
        base_info=AttrDict({
            "base_pos": (random.random()*1920,1020), # position of base of tree
            "base_width": tree_info.base_info.base_width, # half of width of base of tree
        }),
        trunk_info=tree_info.trunk_info,
        branch_info=tree_info.branch_info,
        canopy_info=tree_info.canopy_info,
        color_info=tree_info.color_info
    )

trees = []
    
dragging_node = None

def bring_to_front():
    hwnd = pygame.display.get_wm_info()['window']
    ctypes.windll.user32.ShowWindow(hwnd, 5)      # SW_SHOW
    ctypes.windll.user32.SetForegroundWindow(hwnd)


c = 45
c2 = 0


# --- Pomodoro Widget Setup ---
font = pygame.font.SysFont("Quicksand", 64)
button_font = pygame.font.SysFont("Quicksand", 28)

POMODORO_WORK = 25 * 60   # 25 minutes
POMODORO_BREAK = 5 * 60   # 5 minutes
HWND_TOPMOST = -1
HWND_NOTTOPMOST = -2
SWP_NOMOVE   = 0x0002
SWP_NOSIZE   = 0x0001

class Pomodoro:
    def __init__(self):
        self.is_work = True
        self.time_left = POMODORO_WORK
        self.last_tick = pygame.time.get_ticks()
        self.running = False  # controlled by start/stop button
        self.last_tree = -1000
        self.speed = 10

    def toggle(self):
        self.running = not self.running
        if self.running and self.time_left <= 0:
            self.is_work = True
            self.time_left = POMODORO_WORK + self.speed*3
            self.last_tree = self.time_left
            tree = generateRandomTree()
        if not self.running:
            self.is_work = True
            self.time_left = POMODORO_WORK

    def update(self):
        hwnd = pygame.display.get_wm_info()['window']
        if not self.running:
            self.last_tick = pygame.time.get_ticks()
            SetWindowPos(hwnd, HWND_NOTTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
            return
        
        if not self.is_work and self.running:
            SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
            self.last_tree = self.time_left
        else:
            SetWindowPos(hwnd, HWND_NOTTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
        if self.running and abs(self.time_left - self.last_tree) > 60:
            tree = generateRandomTree()
            self.last_tree = self.time_left
            
        now = pygame.time.get_ticks()
        dt = (now - self.last_tick) / 1000.0
        self.last_tick = now
        self.time_left -= self.speed*dt
        if self.time_left <= 0:
            global raindrops
            # Create a pool of raindrops
            raindrops = [RainDrop(screen_size[0], screen_size[1]) for _ in range(220)]
            # switch modes
            self.is_work = not self.is_work
            self.time_left = POMODORO_WORK if self.is_work else POMODORO_BREAK

    def draw(self, surface):
        if not self.is_work and self.running:
            # Darken full screen
            overlay = pygame.Surface(screen_size, pygame.SRCALPHA)
            overlay.fill((20, 25, 40, 120))  # semi-transparent black
            surface.blit(overlay, (0, 0))

            # "BREAK" text
            break_font = pygame.font.SysFont("Verdana", 80)
            break_font2 = pygame.font.SysFont("Quicksand", 48)
            text_break = break_font.render("time for a break", True, (255, 255, 255))
            surface.blit(
                text_break,
                (screen_size[0]//2 - text_break.get_width()//2,
                 screen_size[1]//2 - text_break.get_height()//2 - 80)
            )

            # Timer under BREAK
            mins = int(self.time_left) // 60
            secs = int(self.time_left) % 60
            timer_text = f"{mins:02}:{secs:02}"
            text_timer = break_font2.render(timer_text, True, (255, 255, 255))
            surface.blit(
                text_timer,
                (screen_size[0]//2 - text_timer.get_width()//2,
                 screen_size[1]//2 + 20)
            )
        else:
            # Normal top-right box for work
            box_w, box_h = 300, 250
            x, y = 1480, 100

            box_surf = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
            pygame.draw.rect(box_surf, (255, 255, 255, 0),
                             (0, 0, box_w, box_h), 0, border_radius=10)
            pygame.draw.rect(box_surf, (255, 255, 255, 255),
                             (0, 0, box_w, box_h), 3, border_radius=10)
            surface.blit(box_surf, (x, y))

            # Timer
            mins = int(self.time_left) // 60
            secs = int(self.time_left) % 60
            timer_text = f"{mins:02}:{secs:02}"
            text_timer = font.render(timer_text, True, (255, 255, 255))
            surface.blit(
                text_timer,
                (x + box_w//2 - text_timer.get_width()//2,
                 y + box_h//2 - text_timer.get_height()//2)
            )

            # Button
            button_text = "Stop Session" if self.running else "Start Session"
            self.button_surface = button_font.render(button_text, True, (255, 255, 255))
            self.button_rect = self.button_surface.get_rect(
                center=(x + box_w//2, y + box_h - 40)
            )
            surface.blit(self.button_surface, self.button_rect)



pomodoro = Pomodoro()

def draw_leaf(surface, x, y, length=40, width=20, color=(90,130,60), angle=0):
    """Draws a simple tapered leaf shape at (x, y)."""
    points = [
        (x, y),  # base
        (x + length/2, y - width/2),
        (x + length, y),
        (x + length/2, y + width/2),
    ]
    # make a surface for rotation
    leaf_surf = pygame.Surface((length+width, width*2), pygame.SRCALPHA)
    pygame.draw.polygon(leaf_surf, color, [(p[0]-x, p[1]-y+width) for p in points])
    rotated = pygame.transform.rotate(leaf_surf, angle)
    rect = rotated.get_rect(center=(x, y))
    surface.blit(rotated, rect)

foreground_surface.fill((0,0,0,0))  # clear previous frame

    # scattered vegetation tufts
for _ in range(25):
    x = random.randint(0, screen_size[0])
    y = screen_size[1]-195
    for _ in range(3):  # cluster of 3 leaves
        length = random.randint(20, 40)
        width = random.randint(8, 18)
        angle = random.randint(-60, 60)
        draw_leaf(foreground_surface, x, y, length, width, foreground_color, angle)

# draw a ground strip across the bottom
pygame.draw.rect(
    foreground_surface,
    vegetation_color,
    (0, screen_size[1]-190, screen_size[0], 190)  # adjust height as desired
)

    # scattered vegetation tufts
for _ in range(25):
    x = random.randint(0, screen_size[0])
    y = screen_size[1]-195
    for _ in range(3):  # cluster of 3 leaves
        length = random.randint(20, 40)
        width = random.randint(8, 18)
        angle = random.randint(-60, 60)
        draw_leaf(foreground_surface, x, y, length, width, vegetation_color, angle)


# --- Audio Setup ---
# --- Rain Effect Setup ---
class RainDrop:
    def __init__(self, screen_w, screen_h):
        self.x = random.randint(0, screen_w*1.5-300)
        self.y = random.randint(-screen_h, 0)
        self.length = 20
        self.speed = random.randint(25,30)
        self.angle = math.radians(80)
        self.dx = self.speed * math.cos(self.angle)
        self.dy = self.speed * math.sin(self.angle)

    def update(self, screen_w, screen_h):
        self.x += self.dx
        self.y += self.dy
        if self.y > 0.75*screen_h or self.x > screen_w:
            self.length -= 4
            if self.length <= 0:
                self.__init__(screen_w, screen_h)

    def draw(self, surface):
        end_x = self.x + self.length * math.cos(self.angle)
        end_y = self.y + self.length * math.sin(self.angle)
        pygame.draw.line(surface, (180, 180, 200, 100), (self.x, self.y), (end_x, end_y), 4)


pygame.mixer.init()
work_music = "music.mp3"
break_music = "rain.mp3"

current_track = None
is_playing = False

def play_with_fade(track, fade_ms=3000, loop=-1):
    """Start a track with fade-in if it's not already playing."""
    global current_track, is_playing
    if current_track != track:
        pygame.mixer.music.fadeout(fade_ms)   # fade out previous
        pygame.mixer.music.load(track)
        pygame.mixer.music.play(loop, fade_ms=fade_ms)
        current_track = track
        is_playing = True
        pomodoro.time_left = POMODORO_WORK if pomodoro.is_work else POMODORO_BREAK

def stop_with_fade(fade_ms=3000):
    """Fade out and stop everything."""
    global current_track, is_playing
    if is_playing:
        pygame.mixer.music.fadeout(fade_ms)
        current_track = None
        is_playing = False
        

# Create a pool of raindrops
raindrops = [RainDrop(screen_size[0], screen_size[1]) for _ in range(150)]

rain_surface = pygame.Surface(surface_size, pygame.SRCALPHA)

while True:
        
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            raise SystemExit
        
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                tree = generateRandomTree()

            if event.key == pygame.K_r:
                trees = []

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if pomodoro.button_rect.collidepoint(event.pos):
                pomodoro.toggle()

    background_surface.fill(bg)
    screen.blit(background_surface, (0,0))

    for surf in growing_surfaces:
        surf.fill((0,0,0,0))

    for tree in trees:
        tree.display()

    for depth in (3,2,1,0):
        screen.blit(surfaces[depth], (0,0))
        screen.blit(growing_surfaces[depth], (0,0))


    screen.blit(foreground_surface, (0,0))

    pomodoro.update()
    pomodoro.draw(screen)


    rain_surface.fill((0,0,0,0))
    # --- Rain Effect During Break ---
    if pomodoro.running and not pomodoro.is_work:
        for drop in raindrops:
            drop.update(screen_size[0], screen_size[1])
            drop.draw(rain_surface)
    screen.blit(rain_surface, (0,0))
    
    pygame.display.flip()
    clock.tick(20)

    # --- Audio State Management ---
    if pomodoro.running:
        if pomodoro.is_work:
            play_with_fade(work_music)
        else:
            play_with_fade(break_music)
    else:
        stop_with_fade()








