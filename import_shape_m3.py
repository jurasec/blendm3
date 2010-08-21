# ##### BEGIN GPL LICENSE BLOCK #####
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
# ##### END GPL LICENCE BLOCK #####

# M3 Importer by Alexander Stante (stante@gmail.com)
#
# This script imports the M3 file into Blender for editing

import bpy
import os

from bpy.props import *
from struct import unpack_from, calcsize
from os.path import basename

# M3 File representation encapsulating file handle
class M3File:
    def __init__(self, filepath):
        self.file = open(filepath, "rb")
        self.ReferenceTable = []
        
    def seek(self, position, offset):
        self.file.seek(position, offset)
        
    def seek(self, position):
        self.file.seek(position, 0)
        
    def skipBytes(self, count):
        self.file.seek(count, 1)

    def readBytes(self, count):
        return unpack_from("<" + str(count) + "B", self.file.read(calcsize("<" + str(count) + "B")))
    
    def readUnsignedInt(self):
        (unsignedInt, ) = unpack_from("<I", self.file.read(calcsize("<I")))
        return unsignedInt
        
    def readUnsignedShort(self):
        (unsignedShort, ) = unpack_from("<H", self.file.read(calcsize("<H")))
        return unsignedShort
        
    def readArrayUnsignedShort(self, count):
        return unpack_from("<" + str(count) + "H", self.file.read(calcsize("<" + str(count) + "H")))
        
    def readArraySignedShort(self, count):
        return unpack_from("<" + str(count) + "h", self.file.read(calcsize("<" + str(count) + "h")))
        
    def readVertex(self):
        return unpack_from("<3f", self.file.read(calcsize("<3f")))
        
    def readString(self, count):
        (string, ) = unpack_from("<" + str(count) + "s", self.file.read(calcsize("<" + str(count) + "s")))
        return string
        
    def readId(self):
        id = self.readString(4)
        return id[::-1]
        
    def readM3Reference(self):
        return M3Reference(self)
        
    def readReferenceEntry(self):
        ref = M3Reference(self)
        
        return self.ReferenceTable[ref.Index]
        
    def readIndices(self, reference):
        faces = []
        count = reference.Count
        offset = reference.Offset
        
        self.file.seek(offset)
        
        for i in range(count):
            faces.append(self.readUnsignedShort())
            
        return faces
    
    def readRegions(self, reference):
        regions = []
        count = reference.Count
        offset = reference.Offset
        
        self.file.seek(offset)
        
        for i in range(count):
            regions.append(M3Region(self))
            
        return regions
        
class M3Reference:
    def __init__(self, file):
        self.Count = file.readUnsignedInt()
        self.Index = file.readUnsignedInt()
        self.Flags = file.readUnsignedInt()
        
class M3Region:

    def __init__(self, file):
        self.D1           = file.readUnsignedInt()
        self.D2           = file.readUnsignedInt()
        self.OffsetVert   = file.readUnsignedInt()
        self.NumVert      = file.readUnsignedInt()
        self.OffsetFaces  = file.readUnsignedInt()
        self.NumFaces     = file.readUnsignedInt()
        self.BoneCount    = file.readUnsignedShort()
        self.IndBone      = file.readUnsignedShort()
        self.NumBone      = file.readUnsignedShort()
        self.s1           = file.readArrayUnsignedShort(3)

# TODO read bat and msec		
class M3Div:

    def __init__(self, file):
        referenceIndices = file.readReferenceEntry()
        referenceRegions = file.readReferenceEntry()
        referenceBat     = file.readReferenceEntry()
        referenceMsec    = file.readReferenceEntry()

        self.Indices = file.readIndices(referenceIndices)
        self.Regions = file.readRegions(referenceRegions)
        self.Bat     = []
        self.Msec    = []


class M3Vertex:
    VERTEX32 = 0
    VERTEX36 = 1
    VERTEX40 = 2
    VERTEX44 = 3
    
    def __init__(self, file, type, flags):
        self.Position   = file.readVertex()
        self.BoneWeight = file.readBytes(4)
        self.BoneIndex  = file.readBytes(4)
        self.Normal     = file.readBytes(4)
        self.UV         = []

        # Vertex type specifies how many UV entries the Vertex format contains
        for i in range(type + 1):
            (u, v) = file.readArraySignedShort(2)
            u = u / 2048.0
            v = v / 2048.0
            
            if (u > 1.0) or (u < 0.0):
                print("WTFu : " + str(u))
            
            if (v > 1.0) or (v < 0.0):
                print("WTFv : " + str(v))

            
            u = 0
            v = 1 - v
            self.UV.append((u,v))
        
        # Further investigation of this flag needed
        if ((flags & 0x200) != 0):
            file.skipBytes(4)
            
        self.Tangent    = file.readBytes(4)

class M3Model23:
    
    def __init__(self):
        self.Flags = 0
        self.Vertices = []
        self.UV1 = []
        self.Faces = []
        
    def read(file):
        m3model = M3Model23()
        file.skipBytes(0x60)
        m3model.Flags = file.readUnsignedInt()

        vertexReference = file.readReferenceEntry()
        viewReference   = file.readReferenceEntry()
        
        uvIndex = 0
        
        if ((m3model.Flags & 0x100000) != 0):
            count = vertexReference.Count // 44
            print("Reading %s vertices, Format: 0x100000, Flags: %s" % (count, hex(m3model.Flags)))
            file.seek(vertexReference.Offset)
            for i in range(count):
                ver = M3Vertex(file, M3Vertex.VERTEX44, m3model.Flags)
                m3model.Vertices.append(ver.Position)
                m3model.UV1.append(ver.UV[uvIndex])
                
        elif ((m3model.Flags & 0x80000) != 0):
            count = vertexReference.Count // 40
            print("Reading %s vertices, Format: 0x80000, Flags: %s" % (count, hex(m3model.Flags)))
            file.seek(vertexReference.Offset)
            for i in range(count):
                ver = M3Vertex(file, M3Vertex.VERTEX40, m3model.Flags)
                m3model.Vertices.append(ver.Position)
                m3model.UV1.append(ver.UV[uvIndex])

        elif ((m3model.Flags & 0x40000) != 0):
            count = vertexReference.Count // 36
            print("Reading %s vertices, Format: 0x40000, Flags: %s" % (count, hex(m3model.Flags)))
            file.seek(vertexReference.Offset)
            for i in range(count):
                ver = M3Vertex(file, M3Vertex.VERTEX36, m3model.Flags)
                m3model.Vertices.append(ver.Position)
                m3model.UV1.append(ver.UV[uvIndex])

        elif ((m3model.Flags & 0x20000) != 0):
            count = vertexReference.Count // 32
            print("Reading %s vertices, Format: 0x20000, Flags: %s" % (count, hex(m3model.Flags)))
            file.seek(vertexReference.Offset)
            for i in range(count):
                ver = M3Vertex(file, M3Vertex.VERTEX32, m3model.Flags)
                m3model.Vertices.append(ver.Position)
                m3model.UV1.append(ver.UV[uvIndex])
                
        else:
            raise Exception('import_m3: !ERROR! Unsupported vertex format. Flags: %s' % hex(m3model.Flags))
        
        file.seek(viewReference.Offset)
        div = M3Div(file)
        
        submeshes = []
        
        for regn in div.Regions:
            offset = regn.OffsetVert
            number = regn.NumVert
            
            vertices = m3model.Vertices[offset:offset + number]
            uvs = m3model.UV1
            faces = []
            
            for j in range(regn.OffsetFaces, regn.OffsetFaces + regn.NumFaces, 3):
                faces.append((div.Indices[j], div.Indices[j+1], div.Indices[j+2]))
                #uvs.append((m3model.UV1[div.Indices[j]], m3model.UV1[div.Indices[j+1]], m3model.UV1[div.Indices[j+1]]))
                
            submeshes.append(Submesh(vertices, faces, uvs))
        
        return submeshes
                    
class M3ReferenceEntry:
    
    def __init__(self, file):
        self.Id     = file.readId()
        self.Offset = file.readUnsignedInt()
        self.Count  = file.readUnsignedInt()
        self.Type   = file.readUnsignedInt()
        
    def print(self):
        print("------------------------------------------------")
        print("Id:     " + str(self.Id))
        print("Offset: " + hex(self.Offset))
        print("Count:  " + hex(self.Count))
        print("Type:   " + hex(self.Type))
        print("------------------------------------------------")
                
class M3Header:

    def __init__(self, file):
        self.Id                   = file.readId()
        self.ReferenceTableOffset = file.readUnsignedInt()
        self.ReferenceTableCount  = file.readUnsignedInt()
        self.ModelCount           = file.readUnsignedInt()
        self.ModelIndex           = file.readUnsignedInt()
        
        if self.Id != b'MD34':
            raise Exception('import_m3: !ERROR! Unsupported file format')
        
        count  = self.ReferenceTableCount
        offset = self.ReferenceTableOffset
        
        file.seek(offset)
        
        for i in range(count):
            file.ReferenceTable.append(M3ReferenceEntry(file))
        
class M3Data:

    def __init__(self, filepath):
        file = M3File(filepath)
        
        # Reading file header
        self.m3Header = M3Header(file)
        
        # Reading model
        modelReference = file.ReferenceTable[self.m3Header.ModelIndex]
        
        if (modelReference.Type != 23):
            raise Exception('import_m3: !ERROR! Unsupported model format: %s' % hex(modelReference.Type))
        
        file.seek(modelReference.Offset)
        self.m3Model = M3Model23.read(file)
        
def createMaterial():
    # Create image texture from image. Change here if the snippet
    # folder is not located in you home directory.
    realpath = os.path.expanduser('H:/Downloads/Work/Assets/Textures/armory_diffuse.dds')
    tex = bpy.data.textures.new('ColorTex')
    tex.type = 'IMAGE'
    tex = tex.recast_type()
    tex.image = bpy.data.images.load(realpath)
    tex.use_alpha = True
    # Create shadeless material and MTex
    mat = bpy.data.materials.new('TexMat')
    mat.shadeless = True
    mat.add_texture(texture = tex,
    texture_coordinates = 'UV',
    map_to = 'COLOR')
    return mat
                
class Submesh:

    def __init__(self, vertices, faces, uv1):
        self.Name = "NONAME"
        self.Vertices = vertices
        self.Faces = faces
        self.UV1 = uv1

def import_m3(context, filepath):
    m3data = M3Data(filepath)
    name = basename(filepath)

    for submesh in m3data.m3Model:
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(submesh.Vertices, [], submesh.Faces)
        
        mesh.add_uv_texture()
        uvtex = mesh.uv_textures[0]
        uvtex.name = "foo"
        
#        for i, texcoord in enumerate(submesh.UV1):
#            data = uvtex.data[i]
#            data.uv1 = texcoord[0]
#            data.uv2 = texcoord[1]
#            data.uv3 = texcoord[2]

        for i, face in enumerate(submesh.Faces):
            data = uvtex.data[i]
            data.uv1 = submesh.UV1[face[0]]
            data.uv2 = submesh.UV1[face[1]]
            data.uv3 = submesh.UV1[face[2]]
            data.uv4 = (0,0)
            
        m = createMaterial()
        
        mesh.update(True)
        ob = bpy.data.objects.new(name, mesh)
        ob.data.add_material(m)
        context.scene.objects.link(ob)

class IMPORT_OT_m3(bpy.types.Operator):
    '''Import from Blizzard M3 file'''
    bl_idname = "import_shape.m3"
    bl_label  = "Import M3"

    filepath = StringProperty(name="File Path", description="Filepath used for importing the M3 file", maxlen= 1024, default= "")
    
    # Options to select import porperties
    IMPORT_MESH      = BoolProperty(name="Import Mesh", description="Import the Model Geometry", default=True)
    IMPORT_NORMALS   = BoolProperty(name="Import Normals", description="Import the Model Normals", default=False)
    IMPORT_MATERIALS = BoolProperty(name="Import Bones", description="Import the Model Bones", default=False)
    
    def poll(self, context):
        return True
        
    def execute(self, context):
        import_m3(context, self.properties.filepath)
        return {'FINISHED'}
        
    def invoke(self, context, event):
        wm = context.manager
        wm.add_fileselect(self)
        return {'RUNNING_MODAL'}
        
def menu_func(self, context):
    self.layout.operator(IMPORT_OT_m3.bl_idname, text="Blizzard M3 (.m3)")

def register():
    bpy.types.register(IMPORT_OT_m3)
    bpy.types.INFO_MT_file_import.append(menu_func)
    
def unregister():
    bpy.types.unregister(IMPORT_OT_m3)
    bpy.types.INFO_MT_file_import.remove(menu_func)

if __name__ == "__main__":
    register()
