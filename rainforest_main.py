from os import environ
environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
from win32gui import SetWindowPos

import ctypes
# Make process DPI aware (Windows only)
ctypes.windll.user32.SetProcessDPIAware()

import numpy as np
import pygame
import math, random, time
import yaml
from attrdict import AttrDict
import copy
import ctypes
import pygetwindow as gw
import win32gui

# load tree information
def loadInfo(path):
    with open(path, "r") as f:
        data = yaml.safe_load(f)
    return toAttrDict(data)

def toAttrDict(obj):
    if isinstance(obj, dict):
        return AttrDict({k: toAttrDict(v) for k, v in obj.items()})
    elif isinstance(obj, list):
        return [toAttrDict(v) for v in obj]
    else:
        return obj

def toDict(obj):
    if isinstance(obj, AttrDict):
        return {k: toDict(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [toDict(i) for i in obj]
    else:
        return obj

tree_infos = loadInfo("tree_info.yaml")
tree_infos = [tree_infos[tree] for tree in list(tree_infos.keys())]
tree_names = [tree.name for tree in tree_infos]
beginning_trees = [tree_names.index(tree_name) for tree_name in \
                   ["Kapok", "Purple Heart", "Big Leaf Mahogany", "Cacao"]]

# load music files
import os
from pydub import AudioSegment

playlist_folder = "playlists"
playlists = [entry.name for entry in os.scandir(playlist_folder) if entry.is_dir()]

def getSongs():
    music_files = [os.path.join(playlist_folder, current_playlist, f) for f in os.listdir(os.path.join(playlist_folder, current_playlist)) if f.endswith(".mp3")]
    return music_files

pygame.init()

info = pygame.display.Info()

# settings
preferences = loadInfo("preferences.yaml")

POMODORO_WORK = float(preferences.settings.work_time_minutes)
POMODORO_BREAK = float(preferences.settings.break_time_minutes)
music_volume = preferences.settings.music_volume
rain_volume = preferences.settings.rain_volume
tree_animations = preferences.settings.tree_animations
rain_animations = preferences.settings.rain_animations
enable_pausing = preferences.settings.enable_pausing
enable_titles = preferences.settings.enable_titles
music_while_paused = preferences.settings.music_while_paused
music_while_break = preferences.settings.music_while_break
enable_blocking = preferences.settings.enable_blocking
current_playlist = preferences.settings.current_playlist
ground_level = preferences.settings.ground_level

music_files = getSongs()


screen_size = info.current_w, info.current_h
surface_size = int(screen_size[0] / screen_size[1] * 1200), 1200

foreground_surface = pygame.Surface((surface_size[0], surface_size[1]+800), pygame.SRCALPHA)
background_surface = pygame.Surface(surface_size)
surfaces = [pygame.Surface(surface_size, pygame.SRCALPHA) for i in range(4)]
growing_surfaces = [pygame.Surface(surface_size, pygame.SRCALPHA) for i in range(4)]
rain_surface = pygame.Surface(surface_size, pygame.SRCALPHA)

surface = pygame.Surface(surface_size)
screen = pygame.display.set_mode(screen_size)
clock = pygame.time.Clock()

pygame.display.set_caption("Rainforest Pomodoro")

bg = (100, 108, 135)
fade = (20, 60, 30)
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

    def display(self, color, surface=None):
        if surface is None: surface = surfaces[0]
        for child in self.children:
            c1 = self.circle
            c2 = child.circle
            poly = circleTangents(c1, c2)
            pygame.draw.polygon(surface, color, poly, 0)
        pygame.draw.circle(surface, color, self.circle.pos, self.circle.r)


class Base():
    def __init__(self, pos, r, angle, children=None):
        if children is None: children = []
        self.pos = pos
        self.r = r
        self.size = r
        self.angle = angle
        self.children = children
        self.height = 0

    def addChild(self, node):
        self.children.append(node)

    def display(self, color, surface=None):
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


def draw_rotated_square_surf(surface, center, size, angle, color):
    cx, cy = center
    s = size / 2

    a, b = s*math.cos(angle), s*math.sin(angle)
    rotated = (
        (a+cx,b+cy),
        (-b+cx,a+cy),
        (-a+cx,-b+cy),
        (b+cx,-a+cy)
    )
    
    pygame.draw.polygon(surface, color, rotated)        

def draw_rotated_square_surf2(surface, center, size, angle_deg, color):
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
    

class Leaf():
    def __init__(self, parent, pos):
        self.parent = parent
        self.pos = pos


# utils

def scaleVec(v, s):
    return v[0] * s, v[1] * s

def addVec(v1, v2):
    return v1[0] + v2[0], v1[1] + v2[1]
            
def weightedAvg(v1, v2, w1, w2):
    return tuple((np.array(v1)*w1 + np.array(v2)*w2) / (w1+w2))

def addFade(color, depth):
    return weightedAvg(fade, color, depth*0.3, 1-depth*0.3)

def addNoise(color, scale=0.5):
    return weightedAvg([random.randint(150,250) for ii in range(3)], color, random.random()*(1-scale), random.random()*scale)

def randomAngle(angle):
    return (random.random()*2*angle-angle) / 180 * math.pi

def randomRange(min_, max_):
    return min_ + (max_-min_) * random.random()
    
def addVector(pos, dist, angle, vstretch=1):
    return (pos[0] + dist*math.cos(angle), pos[1] - dist*math.sin(angle) * vstretch)

def polarToVec(dist, angle):
    return dist*math.cos(angle), -dist*math.sin(angle)


depths = [0,0,0,1,0,0,1,1,0,2,1,0,1,1,2,1,0,0,2,2,1,1,0,3,3,2,0,1,1,1,0,0,0]
num_trees = 0
class Tree():
    def __init__(self, name, base, height, leaves, canopy_info, colors):
        global num_trees
        
        if num_trees > 20: self.depth = random.choice([0,1,1,2,2,2,2,3,3])
        else: self.depth = depths[num_trees]
        self.surface = growing_surfaces[self.depth]
        self.depth_display = min(self.depth, 2.7)

        trees.append(self)
        num_trees += 1
        
        self.name = name
        self.base = base
        self.height = height
        self.leaves = leaves
        self.canopy_info = canopy_info
        self.colors = colors

        # store vars
        self.spread = self.canopy_info.spread
        self.stretch = self.canopy_info.stretch
        self.density = self.canopy_info.density
        self.leaf1 = self.colors.leaf1
        self.leaf2 = self.colors.leaf2
        self.leaf1_w_fade = addFade(self.colors.leaf1, self.depth_display)
        self.leaf2_w_fade = addFade(self.colors.leaf2, self.depth_display)
        self.weighted_leaf = [addFade(weightedAvg(self.leaf1, self.leaf2, w, 1-w), self.depth_display) for w in [0,.1,.2,.3,.4,.5,.6,.7,.8,.9,1.0]]
        self.trunk1 = self.colors.trunk1
        self.trunk2 = self.colors.trunk2
        self.weighted_trunk = [addFade(weightedAvg(self.trunk1, self.trunk2, w, 1-w), self.depth_display) for w in [0,.1,.2,.3,.4,.5,.6,.7,.8,.9,1.0]]


        self.growth = 0.02
        self.generate()


    def generate(self):
        spread = self.spread
        stretch = self.stretch
        density = self.density
        leaf1 = self.leaf1
        leaf2 = self.leaf2
        leaf1_w_fade = self.leaf1_w_fade
        leaf2_w_fade = self.leaf2_w_fade
        
        self.base.r = self.growth**0.5 * self.base.size
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
            for i in range(int(density * self.growth**0.5)):
                r = random.random() ** 2.9 * spread * self.growth
                angle = random.random()*2*math.pi
                pos = addVector(leaf.pos, r, angle, vstretch=stretch)
                w = (r * math.sin(angle) / spread +1)/2 * 0.3 + (math.sin(angle)+1)/2 * 0.7
                color = self.weighted_leaf[int(round(w,1)*10)]
                self.leaves_g.append((pos, 10, random.random()*360, color))

        self.leaves2 = []
        for l1,l2 in zip(self.leaves, self.leaves[1:]):
            if math.dist(l1.pos,l2.pos) > spread*2.5*self.growth: continue
            self.leaves2 += right_angle_points(l1.pos, l2.pos)

        
        self.leaves3 = [
            addVector(avg([l.pos for l in self.leaves]), -range_([l.pos for l in self.leaves])/2.5-10, math.pi/2),
            avg([l.pos for l in self.leaves[:3]]),
            avg([l.pos for l in self.leaves[-3:]])
        ]

        for leaf in self.leaves2:
            for i in range(int(density // 2 * self.growth**0.5)):
                r = random.random() ** 2.9 * spread * 0.7 * self.growth
                angle = random.random()*2*math.pi
                pos = addVector(leaf, r, angle, vstretch=stretch)
                self.leaves2_g.append((pos, 10, random.random()*360, leaf1_w_fade))

        for leaf in self.leaves3:
            for i in range(int(density * self.growth**0.5)):
                r = random.random() ** 2.9 * spread * self.growth
                angle = random.random()*2*math.pi
                pos = addVector(leaf, r, angle, vstretch=stretch)
                self.leaves3_g.append((pos, 10, random.random()*360, leaf2_w_fade))

    def addNode(self, node):
        self.base.addChild(node)

    def display(self):
        if not tree_animations:
            self.growth = 1
        
        if self.growth < 0.8:
            self.growth += 0.03
            self.generate()
        elif self.growth < 1:
            self.growth += 0.01
            self.generate()
        elif self.growth < 2:
            self.growth = 1
            self.generate()
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
                w = max(0.18, min(1, (1.5*node.height/self.height) ** 0.5))
                
            depth = 0
            node2=node
            while node2.children:
                node2 = node2.children[0]
                depth += 1
                if depth > 3: break
            if depth<=3:
                w=0.5
                
            
            node.display(self.weighted_trunk[int(round(w,1)*10)], surface=self.surface)
            parseme += node.children

        for leaf in self.leaves_g:
            draw_rotated_square_surf(self.surface, *leaf)

        for leaf in self.leaves2_g:
            draw_rotated_square_surf(self.surface, *leaf)


class Circle():
    def __init__(self, pos, r):
        self.pos = pos
        self.r = r

    def info(self):
        return self.pos, self.r


def pointToCircleTangents(pos, circle):
    px, py = pos
    cx, cy = circle.pos
    r = circle.r
    dx, dy = px - cx, py - cy
    dist2 = dx*dx + dy*dy
    if dist2 <= r*r:
        return [(circle.pos[0]-circle.r, circle.pos[1]), (circle.pos[0]+circle.r, circle.pos[1])]
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
                dist=polarToVec(curr_height, curr_angle),
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
                    dist=polarToVec(curr_height, curr_angle),
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
                dist=polarToVec(curr_height, curr_angle),
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
                            dist=polarToVec(curr_height, curr_angle),
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
                                dist=polarToVec(curr_height, curr_angle),
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

def generateRandomTree():
    #tree_info = Cacao_info

    if num_trees == 0:
        tree = random.choice(beginning_trees)
        tree_info = tree_infos[tree]
        generateTree(
            name=tree_info.name,
            base_info=AttrDict({
                "base_pos": ((random.random()-0.5)*1000 + surface_size[0]/2, 1100), # position of base of tree
                "base_width": tree_info.base_info.base_width, # half of width of base of tree
            }),
            trunk_info=tree_info.trunk_info,
            branch_info=tree_info.branch_info,
            canopy_info=tree_info.canopy_info,
            color_info=tree_info.color_info
        )
    else:
        tree_info = random.choice(tree_infos)
        generateTree(
            name=tree_info.name,
            base_info=AttrDict({
                "base_pos": (random.random()*surface_size[0], 1100), # position of base of tree
                "base_width": tree_info.base_info.base_width, # half of width of base of tree
            }),
            trunk_info=tree_info.trunk_info,
            branch_info=tree_info.branch_info,
            canopy_info=tree_info.canopy_info,
            color_info=tree_info.color_info
        )
    

def bring_to_front():
    hwnd = pygame.display.get_wm_info()['window']
    ctypes.windll.user32.ShowWindow(hwnd, 5)      # SW_SHOW
    ctypes.windll.user32.SetForegroundWindow(hwnd)


# --- Pomodoro Widget Setup ---
scale = screen_size[1] / 1200

font = pygame.font.SysFont("Quicksand", 84)
edit_font = pygame.font.SysFont("Quicksand", 64)
button_font = pygame.font.SysFont("Quicksand", 36)
button_font2 = pygame.font.SysFont("Segoe UI Symbol", 24)
title_font = pygame.font.Font("Roboto-Medium.ttf", 32)

HWND_TOPMOST = -1
HWND_NOTTOPMOST = -2
SWP_NOMOVE   = 0x0002
SWP_NOSIZE   = 0x0001


def renderText(surface, font, pos, text):
    surf = font.render(text, True, (255,255,255))
    rect = surf.get_rect(topleft=pos)
    surface.blit(surf, rect)

def updateSettings():
    global preferences
    settings_preferences = AttrDict({
        "work_time_minutes": POMODORO_WORK,
        "break_time_minutes": POMODORO_BREAK,
        "music_volume": music_volume,
        "rain_volume": rain_volume,
        "tree_animations": tree_animations,
        "rain_animations": rain_animations,
        "enable_pausing": enable_pausing,
        "enable_titles": enable_titles,
        "music_while_paused": music_while_paused,
        "music_while_break": music_while_break,
        "enable_blocking": enable_blocking,
        "current_playlist": current_playlist,
        "ground_level": ground_level,
    })
    preferences.settings = settings_preferences
    with open("preferences.yaml", "w") as f:
        yaml.dump(toDict(preferences), f, default_flow_style=False)


class Pomodoro:
    def __init__(self):
        self.is_work = True
        self.time_left = POMODORO_WORK
        self.last_tick = pygame.time.get_ticks()
        self.running = False  # controlled by start/stop button
        self.last_tree = -1000
        self.speed = 1

        self.paused = False
        self.settings = False
        self.editing = False
        self.work_edit = "2500"
        self.break_edit = "0500"
        self.save_text = ""
        self.input_active = "none"

        self.pausebutton = PauseButton((1810, 160))
        self.titledisplay = TitleDisplay((1800, 1150))
        
        self.active_slider = None
        self.music_volume_slider = Slider((1590, 120), "music")
        self.rain_volume_slider = Slider((1590, 160), "rain")
        self.tree_animations_checkbox = CheckBox((1590, 200), "tree animations")
        self.rain_animations_checkbox = CheckBox((1590, 240), "rain animations")
        self.enable_pausing_checkbox = CheckBox((1590, 280), "enable pausing")
        self.enable_titles_checkbox = CheckBox((1590, 320), "enable titles")
        self.music_while_paused_checkbox = CheckBox((1590, 360), "music on paused")
        self.music_while_break_checkbox = CheckBox((1590, 400), "music on break")
        self.enable_blocking_checkbox = CheckBox((1590, 440), "enable blocking")

        self.playlist_pos = (1590, 500)
        x, y = self.playlist_pos
        self.playlist_checkboxes = [CheckBox((x, y+40*n+40), f"  {plst}") for n, plst in enumerate(playlists)]

    def handle_click(self, pos):
        """Handle clicks when pomodoro is idle."""

        if self.editing and not self.settings:
            if self.confirm_rect.collidepoint(pos):
                # Apply edits
                global POMODORO_WORK, POMODORO_BREAK
                def to_seconds(s): 
                    m, s = int("00"+s[:-2]), int("00"+s[-2:])
                    return m*60+s
                POMODORO_WORK = to_seconds(self.work_edit)
                POMODORO_BREAK = to_seconds(self.break_edit)
                self.time_left = POMODORO_WORK
                self.editing = False
            elif self.cancel_rect.collidepoint(pos):
                self.editing = False
            elif self.work_rect.collidepoint(pos):
                if self.break_edit == "":
                    self.break_edit = self.save_text
                self.input_active = "work"
                self.save_text = self.work_edit
                self.work_edit = ""
            elif self.break_rect.collidepoint(pos):
                if self.work_edit == "":
                    self.work_edit = self.save_text
                self.input_active = "break"
                self.save_text = self.break_edit
                self.break_edit = ""

        if self.settings:
            if self.music_volume_slider.getRect().collidepoint(pos):
                self.active_slider = self.music_volume_slider
            elif self.rain_volume_slider.getRect().collidepoint(pos):
                self.active_slider = self.rain_volume_slider
            else:
                self.active_slider = None

            if self.tree_animations_checkbox.getRect().collidepoint(pos):
                self.tree_animations_checkbox.updateCheckBox(pos)
            elif self.rain_animations_checkbox.getRect().collidepoint(pos):
                self.rain_animations_checkbox.updateCheckBox(pos)
            elif self.enable_pausing_checkbox.getRect().collidepoint(pos):
                self.enable_pausing_checkbox.updateCheckBox(pos)
            elif self.enable_titles_checkbox.getRect().collidepoint(pos):
                self.enable_titles_checkbox.updateCheckBox(pos)
            elif self.music_while_paused_checkbox.getRect().collidepoint(pos):
                self.music_while_paused_checkbox.updateCheckBox(pos)
            elif self.music_while_break_checkbox.getRect().collidepoint(pos):
                self.music_while_break_checkbox.updateCheckBox(pos)
            elif self.enable_blocking_checkbox.getRect().collidepoint(pos):
                self.enable_blocking_checkbox.updateCheckBox(pos)
            else:
                for playlist_checkbox in self.playlist_checkboxes:
                    if playlist_checkbox.getRect().collidepoint(pos):
                        playlist_checkbox.updateCheckBox(pos)

        if self.running and self.is_work and enable_pausing:
            if self.pausebutton.getRect().collidepoint(pos):
                self.paused = not self.paused

                if self.paused and not music_while_paused:
                    pygame.mixer.music.pause()
                else:
                    pygame.mixer.music.unpause()


        if self.settings_rect.collidepoint(pos):
            self.settings = not self.settings
            if not self.settings:
                updateSettings()

        if not self.running and not self.settings and self.timer_rect.collidepoint(pos):
            if not self.editing:
                self.work_edit = f"00{POMODORO_WORK//60}"[-2:]+f"00{POMODORO_WORK%60}"[-2:]
                self.break_edit = f"00{POMODORO_BREAK//60}"[-2:]+f"00{POMODORO_BREAK%60}"[-2:]
                self.input_active = "none"
            self.editing = True

    def handle_drag(self, pos):
        if self.active_slider:
            self.active_slider.updateSlider(pos)

    def handle_key(self, event):
        if not self.editing: return
        target = self.work_edit if self.input_active=="work" else self.break_edit
        if event.key == pygame.K_TAB:
            self.input_active = "break" if self.input_active=="work" else "work"
        elif event.key == pygame.K_BACKSPACE:
            target = target[:-1]
        elif event.key == pygame.K_RETURN:
            self.input_active = "none"
        elif event.unicode.isdigit() and len(target) < 4:
            target += event.unicode
        if self.input_active=="work": self.work_edit = target
        elif self.input_active=="break": self.break_edit = target

    def toggle(self):
        if self.editing:
            return
        if self.running and not self.is_work:
            return
        self.paused = False
        pygame.mixer.music.unpause()
        self.running = not self.running
        if self.running and self.time_left <= 0:
            self.is_work = True
            self.time_left = POMODORO_WORK + self.speed*3
            self.last_tree = self.time_left
            tree = generateRandomTree()
        if not self.running:
            self.is_work = True
            self.time_left = POMODORO_WORK
        updateSettings()

    def update(self):
        hwnd = pygame.display.get_wm_info()['window']
        if not self.running:
            self.last_tick = pygame.time.get_ticks()
            SetWindowPos(hwnd, HWND_NOTTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
            return
        
        if not self.is_work and self.running and enable_blocking:
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
        if not self.paused:
            self.time_left -= self.speed*dt
        if self.time_left <= 0:
            global raindrops
            # Create a pool of raindrops
            raindrops = []
            # switch modes
            self.is_work = not self.is_work
            self.time_left = POMODORO_WORK if self.is_work else POMODORO_BREAK

    def draw(self, surface):
        if not self.is_work and self.running:
            global raindrops
            if rain_animations:
                # Darken full screen
                overlay = pygame.Surface(surface_size, pygame.SRCALPHA)
                overlay.fill((20, 25, 40, 120))  # semi-transparent black
                surface.blit(overlay, (0, 0))
                if not raindrops:
                    raindrops = [RainDrop(screen_size[0], screen_size[1]) for _ in range(350)]
            else:
                raindrops = []

            # "BREAK" text
            break_font = pygame.font.SysFont("Verdana", int(80))
            break_font2 = pygame.font.SysFont("Quicksand", int(48))
            text_break = break_font.render("time for a break", True, (255, 255, 255))
            surface.blit(
                text_break,
                (surface_size[0]//2 - text_break.get_width()//2,
                 surface_size[1]//2 - text_break.get_height()//2 - 80)
            )

            # Timer under BREAK
            mins = int(self.time_left) // 60
            secs = int(self.time_left) % 60
            timer_text = f"{mins:02}:{secs:02}"
            text_timer = break_font2.render(timer_text, True, (255, 255, 255))
            surface.blit(
                text_timer,
                (surface_size[0]//2 - text_timer.get_width()//2,
                 surface_size[1]//2 + 20)
            )
        
        box_w, box_h = int(300), int(250)
        buffer = 50
        x, y = surface_size[0] - box_w - buffer, buffer
        
        if self.settings:
            box_w, box_h = int(300), int(1100)
            buffer = 50
            x, y = surface_size[0] - box_w - buffer, buffer
            pygame.draw.rect(surface, (255,255,255), (x,y,box_w,box_h), 3, border_radius=10)

            self.music_volume_slider.draw(surface)
            self.rain_volume_slider.draw(surface)
            self.tree_animations_checkbox.draw(surface)
            self.rain_animations_checkbox.draw(surface)
            self.enable_pausing_checkbox.draw(surface)
            self.enable_titles_checkbox.draw(surface)
            self.music_while_paused_checkbox.draw(surface)
            self.music_while_break_checkbox.draw(surface)
            self.enable_blocking_checkbox.draw(surface)

            renderText(surface, button_font, self.playlist_pos, "playlists:")
            for playlist_checkbox in self.playlist_checkboxes:
                playlist_checkbox.draw(surface)
                
        elif not(not self.is_work and self.running):
            pygame.draw.rect(surface, (255,255,255), (x,y,box_w,box_h), 3, border_radius=10)

            if self.editing:
                # Draw editable 00:00/00:00
                work_color  = (255, 255, 255) if self.input_active=="work" else (180, 180, 180)
                break_color = (255, 255, 255) if self.input_active=="break" else (180, 180, 180)

                work_text = ("0000"+self.work_edit)[-4:]
                work_text = work_text[:2] + ":" + work_text[2:]
                work_surf  = edit_font.render(work_text, True, work_color)
                break_text = ("0000"+self.break_edit)[-4:]
                break_text = break_text[:2] + ":" + break_text[2:]
                break_surf = edit_font.render(break_text, True, break_color)
                slash_surf = edit_font.render("/", True, (255,255,255))
                
                # Position side by side
                total_w = work_surf.get_width() + slash_surf.get_width() + break_surf.get_width()
                center_x = x + box_w//2
                center_y = y + box_h//2

                self.work_rect  = work_surf.get_rect(midright=(center_x - total_w//2 + work_surf.get_width(), center_y))
                slash_rect = slash_surf.get_rect(midleft=(self.work_rect.right, center_y))
                self.break_rect = break_surf.get_rect(midleft=(slash_rect.right, center_y))

                # Save rect so clicks know where timer is
                self.timer_rect = pygame.Rect(self.work_rect.left, self.work_rect.top,
                                              self.break_rect.right - self.work_rect.left,
                                              self.work_rect.height)

                # Blit them
                surface.blit(work_surf, self.work_rect)
                surface.blit(slash_surf, slash_rect)
                surface.blit(break_surf, self.break_rect)

                # Confirm / Cancel buttons
                check = button_font2.render("✔", True, (255,255,255))
                cross = button_font2.render("✖", True, (255,255,255))
                self.confirm_rect = check.get_rect(center=(x+box_w//2+30, y+box_h//2+60))
                self.cancel_rect = cross.get_rect(center=(x+box_w//2-30, y+box_h//2+60))
                surface.blit(check, self.confirm_rect)
                surface.blit(cross, self.cancel_rect)
            else:
                # Show normal timer + button
                mins = int(self.time_left) // 60
                secs = int(self.time_left) % 60
                timer_text = font.render(f"{mins:02}:{secs:02}", True, (255,255,255))
                self.timer_rect = timer_text.get_rect(center=(x+box_w//2, y+box_h//2))
                surface.blit(timer_text, self.timer_rect)

                button_text = "Stop Session" if self.running else "Start Session"
                self.button_surface = button_font.render(button_text, True, (255,255,255))
                self.button_rect = self.button_surface.get_rect(center=(x+box_w//2, y+box_h-40))
                surface.blit(self.button_surface, self.button_rect)

                if enable_pausing and self.running and self.is_work:
                    self.pausebutton.draw(surface)
                        
        
        gear_size = 20
        self.settings_rect = pygame.Rect(x + box_w - gear_size - 20, y + 20, gear_size, gear_size)
        pygame.draw.circle(surface, (255, 255, 255), self.settings_rect.center, gear_size//2, 4)
        for i in range(8):
            angle = i * (math.pi/4)
            tx = int(self.settings_rect.centerx + math.cos(angle) * gear_size//2)
            ty = int(self.settings_rect.centery + math.sin(angle) * gear_size//2)
            pygame.draw.circle(surface, (255, 255, 255), (tx, ty), 3.5)

        self.titledisplay.draw(surface)


class TitleDisplay():
    def __init__(self, pos):
        self.pos = pos
        
        self.text = "Now Playing: Ancient Paths"
        self.opacity = 0
        self.fade = "out"
        self.hold = 0

    def update(self, song):
        song = song.replace('-',' ').replace('_',' ')
        self.text = f"Now Playing: {song}"
        self.opacity = 0
        self.fade = "in"
        self.hold = 0

    def draw(self, surface):
        #text = current_track
        text_surface = title_font.render(self.text, True, (255,255,255))
        text_surface.set_alpha(self.opacity)
        text_rect = text_surface.get_rect()
        text_rect.midright = self.pos
        surface.blit(text_surface, text_rect)

        if self.fade == "in":
            self.opacity = min(255, self.opacity+5)
            if self.opacity == 255:
                self.hold = 60
                self.fade = "out"
                
        if self.fade == "out":
            if self.hold:
                self.hold -= 1
            else:
                self.opacity = max(0, self.opacity-5)
        

class PauseButton():
    def __init__(self, pos):
        self.pos = pos

    def getRect(self):
        x, y = self.pos
        s = 25
        w = s
        h = s
        return pygame.Rect(x,y,w,h)

    def draw(self, surface):
        x, y = self.pos
        s = 25
        pos = self.pos
        pos1 = (x, y+s)
        pos2 = (x + s*math.sin(math.pi/3), y + s*math.cos(math.pi/3))
        if pomodoro.paused:
            pygame.draw.polygon(surface, (255,255,255), [pos, pos1, pos2])
        else:
            pygame.draw.rect(surface, (255,255,255), (x,y,s/3,s))
            pygame.draw.rect(surface, (255,255,255), (x+2*s/3,y,s/3,s))


class Slider():
    def __init__(self, pos, text):
        self.pos = pos
        self.text = text

    def draw(self, surface):
        x, y = self.pos
        renderText(surface, button_font, (x, y), self.text)

        match self.text:
            case "music":
                scale = music_volume
            case "rain":
                scale = rain_volume
                
        pygame.draw.rect(surface, (255,255,255), (x+110,y+8,150*scale,10), border_radius=10)
        pygame.draw.rect(surface, (255,255,255), (x+110,y+8,150,10), 2, border_radius=10)

    def getRect(self):
        x, y = self.pos
        x = x + 110
        y = y + 8
        w = 150
        h = 10
        return pygame.Rect(x,y,w,h)

    def updateSlider(self, mousepos):
        x, y = self.pos
        x = x + 110
        y = y + 8
        w = 150

        scale = min(1, max(0, (mousepos[0] - x) / w))
        match self.text:
            case "music":
                global music_volume
                music_volume = scale
                if current_track != break_music:
                    pygame.mixer.music.set_volume(music_volume)
            case "rain":
                global rain_volume
                rain_volume = scale
                if current_track == break_music:
                    pygame.mixer.music.set_volume(rain_volume)


class CheckBox():
    def __init__(self, pos, text):
        self.pos = pos
        self.text = text

    def draw(self, surface):
        x, y = self.pos
        renderText(surface, button_font, (x, y), self.text)

        match self.text:
            case "tree animations":
                checked = tree_animations
            case "rain animations":
                checked = rain_animations
            case "enable pausing":
                checked = enable_pausing
            case "enable titles":
                checked = enable_titles
            case "music on paused":
                checked = music_while_paused
            case "music on break":
                checked = music_while_break
            case "enable blocking":
                checked = enable_blocking
            case _:
                checked = self.text.strip() == current_playlist

        pygame.draw.rect(surface, (255,255,255), (x+230,y+2,20,20), [2,0][checked], border_radius=3)

    def getRect(self):
        x, y = self.pos
        x = x + 230
        y = y + 2
        w = 20
        h = 20
        return pygame.Rect(x,y,w,h)

    def updateCheckBox(self, mousepos):
        match self.text:
            case "tree animations":
                global tree_animations
                tree_animations = not tree_animations
            case "rain animations":
                global rain_animations
                rain_animations = not rain_animations
            case "enable pausing":
                global enable_pausing
                enable_pausing = not enable_pausing
            case "enable titles":
                global enable_titles
                enable_titles = not enable_titles
            case "music on paused":
                global music_while_paused
                music_while_paused = not music_while_paused
                if music_while_paused:
                    pygame.mixer.music.unpause()
                else:
                    if pomodoro.paused:
                        pygame.mixer.music.pause()
            case "music on break":
                global music_while_break
                music_while_break = not music_while_break
                if pomodoro.running and not pomodoro.is_work:
                    if not music_while_break:
                        stop_with_fade()
            case "enable blocking":
                global enable_blocking
                enable_blocking = not enable_blocking
            case _:
                global current_playlist, music_files
                current_playlist = self.text.strip()
                music_files = getSongs()
                stop_with_fade()

        



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

class RainDrop:
    def __init__(self, screen_w, screen_h):
        self.depth = random.choice([0,1])
        self.x = random.randint(0, int(screen_w*1.5)) - 500
        self.y = random.randint(-screen_h, 0)
        self.length = 20 + 10*self.depth
        self.speed = random.randint(25,30) + 4*self.depth
        self.angle = math.radians(80)
        self.dx = self.speed * math.cos(self.angle)
        self.dy = self.speed * math.sin(self.angle)

    def update(self, screen_w, screen_h):
        self.x += self.dx
        self.y += self.dy
        if self.y > ground_level-100 or self.x > screen_w:
            self.length -= 6
            if self.length <= 0:
                self.__init__(screen_w, screen_h)

    def draw(self, surface):
        end_x = self.x + self.length * math.cos(self.angle)
        end_y = self.y + self.length * math.sin(self.angle)
        pygame.draw.line(surface, (180, 180, 200, 140 - 80*self.depth), (self.x, self.y), (end_x, end_y), 4)

# --- Audio Setup ---
pygame.mixer.init()

current_track = None
is_playing = False

MUSIC_END = pygame.USEREVENT + 1
pygame.mixer.music.set_endevent(MUSIC_END)

break_music = "rain.mp3"  # always used for breaks

class MusicFader():
    def __init__(self):
        self.fade_speed = 0
        self.current_fade = -1
        self.last_time = time.time()

    def fadeout(self, fade_ms, volume):
        self.fade_speed = volume / (fade_ms/1000)
        self.current_fade = volume

        self.last_time = time.time()

    def update(self):
        curr_time = time.time()
        if self.current_fade:
            self.current_fade = max(0, self.current_fade - self.fade_speed * (curr_time-self.last_time))
            pygame.mixer.music.set_volume(self.current_fade)
        if self.current_fade == 0:
            volume = music_volume if current_track != break_music else rain_volume
            pygame.mixer.music.set_volume(volume)
        self.last_time = curr_time
            
            
music_fader = MusicFader()
def play_with_fade(track, fade_ms=3000, loop=0):
    """Start a track with fade-in if it's not already playing."""
    global current_track, is_playing
    
    if current_track != track:
        pygame.mixer.music.fadeout(fade_ms)   # fade out previous
        if music_fader.current_fade == -1:
            volume = music_volume if current_track != break_music else rain_volume
            music_fader.fadeout(fade_ms, volume)
        else:
            print(f"Now Playing: {track}")
            music_fader.current_fade = -1
            pygame.mixer.music.load(track)
            pygame.mixer.music.play(loop, fade_ms=fade_ms)

            if pomodoro.paused and not music_while_paused:
                pygame.mixer.music.pause()
            
            if track != break_music:
                pygame.mixer.music.set_volume(music_volume)
                if enable_titles:
                    pomodoro.titledisplay.update(track.split('\\')[-1][:-4])
            else:
                pygame.mixer.music.set_volume(rain_volume)
            
            is_playing = True
            current_track = track
    return track

def stop_with_fade(fade_ms=3000):
    """Fade out and stop everything."""
    global current_track, is_playing
    if is_playing:
        pygame.mixer.music.fadeout(fade_ms)
        current_track = None
        is_playing = False

def play_random_song():
    """Pick and play a random mp3 from the playlist folder."""
    if not music_files:
        return None
    track = current_track
    while track == current_track:
        track = random.choice(music_files)
    return play_with_fade(track)


pomodoro = Pomodoro()

foreground_color = (70, 90, 40)   # dark brownish-green
vegetation_color = (75, 110, 45)  # lighter green for small plants
foreground_surface.fill((0,0,0,0))  # clear previous frame

    # scattered vegetation tufts
for _ in range(25):
    x = random.randint(0, surface_size[0])
    y = 1100-20
    for _ in range(3):  # cluster of 3 leaves
        length = random.randint(20, 40)
        width = random.randint(8, 18)
        angle = random.randint(-60, 60)
        draw_leaf(foreground_surface, x, y, length, width, foreground_color, angle)

# draw a ground strip across the bottom
pygame.draw.rect(
    foreground_surface,
    vegetation_color,
    (0, 1100-15, surface_size[0], 800)  # adjust height as desired
)

    # scattered vegetation tufts
for _ in range(25):
    x = random.randint(0, surface_size[0])
    y = 1100-20
    for _ in range(3):  # cluster of 3 leaves
        length = random.randint(20, 40)
        width = random.randint(8, 18)
        angle = random.randint(-60, 60)
        draw_leaf(foreground_surface, x, y, length, width, vegetation_color, angle)


# --- Ground Level Menu Icon ---
icon_size = 30
icon_padding = 20
icon_rect = pygame.Rect(surface_size[0] - icon_size - icon_padding, ground_level, icon_size, icon_size)
dragging_ground = False

def draw_menu_icon(surface, rect, color=(60, 90, 60)):
    bar_height = 5
    spacing = 5
    for i in range(3):
        y = rect.y + i*(bar_height+spacing)
        pygame.draw.rect(surface, color, (rect.x, y, rect.w, bar_height))


# Create a pool of raindrops
raindrops = [RainDrop(screen_size[0], screen_size[1]) for _ in range(150)]
trees = []
music_start = False
while True:
    music_fader.update()
        
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            raise SystemExit

        elif event.type == MUSIC_END:
            if not music_start:
                is_playing = False

        elif event.type == pygame.MOUSEBUTTONDOWN:
            surface_pos = event.pos[0]/scale, event.pos[1]/scale
            pomodoro.handle_click(surface_pos)
            if not (pomodoro.running and not pomodoro.is_work):
                if pomodoro.button_rect.collidepoint(surface_pos):
                    pomodoro.toggle()
                elif icon_rect.collidepoint(surface_pos):
                    dragging_ground = True

        elif event.type == pygame.KEYDOWN:
            pomodoro.handle_key(event)
            if event.key == pygame.K_SPACE and not pomodoro.editing:
                generateRandomTree()

        elif event.type == pygame.MOUSEBUTTONUP:
            dragging_ground = False

        elif event.type == pygame.MOUSEMOTION and dragging_ground and not pomodoro.running:
            # Update ground level with mouse Y
            new_level = event.pos[1] / scale - 15
            ground_level = max(600, min(surface_size[1]-50, new_level))  # clamp between 600px and bottom
            icon_rect.y = ground_level

        if pygame.mouse.get_pressed()[0]:
            mouse_x, mouse_y = pygame.mouse.get_pos()
            surface_pos = mouse_x / scale, mouse_y / scale
            pomodoro.handle_drag(surface_pos)


    background_surface.fill(bg)
    surface.blit(background_surface, (0,0))

    for surf in growing_surfaces:
        surf.fill((0,0,0,0))

    trees = [tree for tree in trees if tree.growth < 2]

    for tree in trees:
        tree.display()

    for depth in (3,2,1,0):
        surface.blit(surfaces[depth], (0,ground_level-1100))
        surface.blit(growing_surfaces[depth], (0,ground_level-1100))


    surface.blit(foreground_surface, (0,ground_level-1100))

    if not pomodoro.running:
        draw_menu_icon(surface, icon_rect)

    rain_surface.fill((0,0,0,0))
    # --- Rain Effect During Break ---
    if pomodoro.running and not pomodoro.is_work:
        if not rain_animations:
            raindrops = []
            
        for drop in raindrops:
            drop.update(surface_size[0], surface_size[1])
            drop.draw(rain_surface)
    surface.blit(rain_surface, (0,0))

    pomodoro.update()
    pomodoro.draw(surface)

    pygame.transform.smoothscale(surface, screen_size, screen)
    pygame.display.flip()
    clock.tick(20)

    music_start = False
    # --- Audio State Management ---
    if pomodoro.running:
        if pomodoro.is_work or music_while_break:
            if not is_playing or current_track==break_music:
                play_random_song()
                music_start = True
        else:
            play_with_fade(break_music, loop=-1)  # loop rain endlessly
    else:
        stop_with_fade()









