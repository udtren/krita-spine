import json
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from krita import InfoObject

try:
    from PyQt5.QtCore import QRect, Qt
    from PyQt5.QtGui import QImage
except ImportError:
    from PySide6.QtCore import QRect, Qt
    from PySide6.QtGui import QImage


def _qimage_format_rgba8888():
    fmt = getattr(QImage, "Format_RGBA8888", None)
    if fmt is not None:
        return fmt
    return QImage.Format.Format_RGBA8888


def _qt_ignore_aspect_ratio():
    value = getattr(Qt, "IgnoreAspectRatio", None)
    if value is not None:
        return value
    return Qt.AspectRatioMode.IgnoreAspectRatio


def _qt_smooth_transformation():
    value = getattr(Qt, "SmoothTransformation", None)
    if value is not None:
        return value
    return Qt.TransformationMode.SmoothTransformation


_TAG_RE = re.compile(r"\[([^\]:]+)(?::([^\]]*))?\]")
_VALID_GROUP_TAGS = {
    "bone",
    "skin",
    "folder",
    "ignore",
    "merge",
    "name",
    "scale",
    "slot",
    "trim",
}
_VALID_LAYER_TAGS = {
    "bone",
    "skin",
    "folder",
    "ignore",
    "mesh",
    "path",
    "scale",
    "slot",
    "trim",
}
_BLEND_MAP = {
    "multiply": "multiply",
    "screen": "screen",
    "add": "additive",
    "linear dodge": "additive",
    "linear_dodge": "additive",
    "linearDodge": "additive",
}


class SpineExportError(Exception):
    pass


def _clean_node_name(name):
    return _TAG_RE.sub("", name or "").strip()


def active_group_export_name(document):
    node = document.activeNode()
    if node is None or node.type() != "grouplayer":
        raise SpineExportError(
            "The active node is not a group layer. Select a group layer as the "
            "active node before exporting."
        )
    current = _clean_node_name(node.name())
    parent = node.parentNode()
    parent_name = ""
    if parent is not None and parent.type() == "grouplayer":
        parent_name = _clean_node_name(parent.name())
    if parent_name:
        return "{0}_{1}".format(parent_name, current)
    return current


@dataclass
class ExportSettings:
    json_path: str
    images_dir: str
    scale: float = 1.0
    padding: int = 1
    trim_whitespace: bool = True
    write_json: bool = True
    write_images: bool = True
    write_template: bool = False
    legacy_json: bool = True


@dataclass
class ExportResult:
    attachment_count: int
    json_path: Optional[str]
    images_dir: Optional[str]


@dataclass
class LayerInfo:
    node: object
    parent_chain: List[object]
    name: str
    clean_name: str
    attachment_name: str = ""
    attachment_path: str = ""
    placeholder_name: str = ""
    slot_name: str = ""
    skin_name: str = "default"
    bone_name: str = "root"
    scale: float = 1.0
    mesh: Optional[str] = None
    rect: Optional[QRect] = None
    exported_size: Tuple[int, int] = (0, 0)
    spine_xy: Tuple[float, float] = (0.0, 0.0)
    blend: Optional[str] = None
    visible: bool = True


@dataclass
class BoneInfo:
    name: str
    parent: Optional[str] = None
    x: float = 0.0
    y: float = 0.0
    has_position: bool = False


@dataclass
class SlotInfo:
    name: str
    bone: str = "root"
    attachment: Optional[str] = None
    blend: Optional[str] = None
    layers: List[LayerInfo] = field(default_factory=list)


class SpineExporter:
    def __init__(self, document, settings: ExportSettings):
        self.document = document
        self.settings = settings
        self.layers: List[LayerInfo] = []
        self.bones: Dict[str, BoneInfo] = {"root": BoneInfo("root")}
        self.slots: Dict[str, SlotInfo] = {}
        self.skin_order: List[str] = []
        self.errors: List[str] = []

    def export(self) -> ExportResult:
        if (
            not self.settings.write_json
            and not self.settings.write_images
            and not self.settings.write_template
        ):
            raise SpineExportError("Enable at least one output option.")
        if self.settings.write_json and not self.settings.json_path:
            raise SpineExportError("Choose a Spine JSON path.")
        if self.settings.write_images and not self.settings.images_dir:
            raise SpineExportError("Choose an images output folder.")

        active_group_export_name(self.document)

        self.document.waitForDone()
        self.document.refreshProjection()

        self._collect_layers()
        if not self.layers:
            raise SpineExportError("No exportable layers found.")

        self._prepare_layers()

        if self.settings.write_images:
            os.makedirs(self.settings.images_dir, exist_ok=True)
            for layer in self.layers:
                self._write_layer_png(layer)

        if self.settings.write_template:
            self._write_template_png()

        if self.settings.write_json:
            os.makedirs(
                os.path.dirname(os.path.abspath(self.settings.json_path)), exist_ok=True
            )
            with open(
                self.settings.json_path, "w", encoding="utf-8", newline="\n"
            ) as fh:
                json.dump(self._build_json(), fh, ensure_ascii=False, indent=2)
                fh.write("\n")

        return ExportResult(
            attachment_count=len(self.layers),
            json_path=self.settings.json_path if self.settings.write_json else None,
            images_dir=self.settings.images_dir if self.settings.write_images else None,
        )

    def _collect_layers(self):
        root = self.document.rootNode()
        for node in root.childNodes():
            self._walk_node(node, [])

    def _walk_node(self, node, parents: List[object]):
        name = node.name()
        node_type = node.type()
        if self._has_tag(node, "ignore"):
            return
        if not self._effective_visible(node, parents):
            return
        if node_type in (
            "transparencymask",
            "filtermask",
            "transformmask",
            "selectionmask",
            "colorizemask",
        ):
            return
        if self._has_tag(node, "overlay"):
            return

        is_group = node_type == "grouplayer"
        if is_group and self._has_tag(node, "merge"):
            if self._has_exportable_projection(node):
                self.layers.append(
                    LayerInfo(
                        node=node,
                        parent_chain=list(parents),
                        name=name,
                        clean_name=self._strip_tags(name),
                        visible=node.visible(),
                    )
                )
            return
        if is_group:
            for child in node.childNodes():
                self._walk_node(child, parents + [node])
            return

        if self._has_exportable_projection(node):
            self.layers.append(
                LayerInfo(
                    node=node,
                    parent_chain=list(parents),
                    name=name,
                    clean_name=self._strip_tags(name),
                    visible=node.visible(),
                )
            )

    def _prepare_layers(self):
        for layer in self.layers:
            clean = self._apply_name_patterns(
                layer.clean_name or layer.name, layer.parent_chain
            )
            clean = clean[:-4] if clean.lower().endswith(".png") else clean
            if not clean:
                raise SpineExportError(
                    "Layer name is empty after removing tags: {0}".format(
                        self._path(layer)
                    )
                )

            folder_path = self._folder_path(layer.parent_chain + [layer.node])
            path_tag = self._tag_value(
                layer.node, "path", include_parents=layer.parent_chain
            )
            layer.attachment_name = (
                clean if clean.startswith("/") else folder_path + clean
            )
            layer.attachment_name = layer.attachment_name.lstrip("/")
            if path_tag:
                layer.attachment_path = (
                    path_tag[1:] if path_tag.startswith("/") else folder_path + path_tag
                )
            else:
                layer.attachment_path = layer.attachment_name
            layer.attachment_path = (
                layer.attachment_path[:-4]
                if layer.attachment_path.lower().endswith(".png")
                else layer.attachment_path
            )

            layer.skin_name = self._skin_name(layer.parent_chain + [layer.node])
            if layer.skin_name != "default" and layer.attachment_name.startswith(
                layer.skin_name + "/"
            ):
                layer.placeholder_name = layer.attachment_name[
                    len(layer.skin_name) + 1 :
                ]
            else:
                layer.placeholder_name = layer.attachment_name
            layer.slot_name = (
                self._tag_value(layer.node, "slot", include_parents=layer.parent_chain)
                or clean
            )
            layer.bone_name = self._bone_name(layer.parent_chain + [layer.node])
            layer.scale = self._float_tag(layer, "scale", 1.0)
            layer.mesh = self._tag_value(
                layer.node, "mesh", include_parents=layer.parent_chain, allow_empty=True
            )
            layer.blend = self._blend(layer.node)
            layer.rect = self._export_rect(layer)

            if (
                layer.rect is None
                or layer.rect.width() <= 0
                or layer.rect.height() <= 0
            ):
                raise SpineExportError(
                    "Layer has no visible pixels: {0}".format(self._path(layer))
                )

            w = layer.rect.width() + self.settings.padding * 2
            h = layer.rect.height() + self.settings.padding * 2
            layer.exported_size = (
                max(1, int(round(w * self.settings.scale))),
                max(1, int(round(h * self.settings.scale))),
            )
            center_x = layer.rect.x() + layer.rect.width() / 2.0
            center_y = layer.rect.y() + layer.rect.height() / 2.0
            layer.spine_xy = (
                center_x * self.settings.scale,
                (self.document.height() - center_y) * self.settings.scale,
            )
            self._register_bone(layer)
            self._register_slot(layer)
            if layer.skin_name not in self.skin_order:
                self.skin_order.append(layer.skin_name)

        self._check_duplicates()

    def _register_bone(self, layer: LayerInfo):
        if layer.bone_name == "root":
            return
        parent_bone = self._parent_bone_name(layer.parent_chain)
        bone = self.bones.get(layer.bone_name)
        if bone is None:
            bone = BoneInfo(
                layer.bone_name, None if parent_bone == "root" else parent_bone
            )
            self.bones[layer.bone_name] = bone
        rect = layer.rect
        if rect is not None and not bone.has_position:
            bone.x = (rect.x() + rect.width() / 2.0) * self.settings.scale
            bone.y = (
                self.document.height() - (rect.y() + rect.height() / 2.0)
            ) * self.settings.scale
            bone.has_position = True

    def _register_slot(self, layer: LayerInfo):
        slot = self.slots.get(layer.slot_name)
        if slot is None:
            slot = SlotInfo(layer.slot_name, layer.bone_name)
            self.slots[layer.slot_name] = slot
        if slot.attachment is None and layer.visible:
            slot.attachment = layer.placeholder_name
        if not slot.blend and layer.blend:
            slot.blend = layer.blend
        slot.layers.append(layer)

    def _check_duplicates(self):
        seen = set()
        for layer in self.layers:
            key = (layer.skin_name, layer.slot_name, layer.placeholder_name)
            if key in seen:
                raise SpineExportError(
                    "Duplicate attachment placeholder '{0}' in skin '{1}', slot '{2}'.".format(
                        layer.placeholder_name,
                        layer.skin_name,
                        layer.slot_name,
                    )
                )
            seen.add(key)

    def _build_json(self):
        data = {
            "skeleton": {"images": self._json_images_path()},
            "KritaToSpine": {
                "scale": self.settings.scale,
                "padding": self.settings.padding,
                "trim": self.settings.trim_whitespace,
            },
            "bones": self._json_bones(),
            "slots": self._json_slots(),
            "animations": {"animation": {}},
        }
        skins = self._json_skins()
        if skins:
            data["skins"] = skins
        return data

    def _json_bones(self):
        bones = [{"name": "root"}]
        for name, bone in self.bones.items():
            if name == "root":
                continue
            item = {"name": name}
            if bone.parent:
                item["parent"] = bone.parent
            if bone.has_position:
                item["x"] = round(bone.x, 4)
                item["y"] = round(bone.y, 4)
            bones.append(item)
        return bones

    def _json_slots(self):
        slots = []
        for slot in self.slots.values():
            item = {"name": slot.name, "bone": slot.bone or "root"}
            if slot.attachment:
                item["attachment"] = slot.attachment
            if slot.blend:
                item["blend"] = slot.blend
            slots.append(item)
        return slots

    def _json_skins(self):
        if self.settings.legacy_json:
            skins = {}
            for skin in self.skin_order:
                skin_slots = {}
                for slot in self.slots.values():
                    attachments = self._attachments_for_slot(slot, skin)
                    if attachments:
                        skin_slots[slot.name] = attachments
                if skin_slots:
                    skins[skin] = skin_slots
            return skins

        skins = []
        for skin in self.skin_order:
            attachments_by_slot = {}
            for slot in self.slots.values():
                attachments = self._attachments_for_slot(slot, skin)
                if attachments:
                    attachments_by_slot[slot.name] = attachments
            if attachments_by_slot:
                skins.append({"name": skin, "attachments": attachments_by_slot})
        return skins

    def _attachments_for_slot(self, slot: SlotInfo, skin: str):
        attachments = {}
        for layer in slot.layers:
            if layer.skin_name != skin:
                continue
            attachment = self._attachment_json(layer)
            attachments[layer.placeholder_name] = attachment
        return attachments

    def _attachment_json(self, layer: LayerInfo):
        x, y = layer.spine_xy
        width, height = layer.exported_size
        data = {
            "x": round(x, 4),
            "y": round(y, 4),
            "width": width,
            "height": height,
        }
        if layer.attachment_name != layer.placeholder_name:
            data["name"] = layer.attachment_name
        if layer.attachment_path != layer.attachment_name:
            data["path"] = layer.attachment_path
        if layer.scale != 1:
            data["scaleX"] = round(1 / layer.scale, 6)
            data["scaleY"] = round(1 / layer.scale, 6)
        if layer.mesh is not None:
            if layer.mesh:
                data.update({"type": "linkedmesh", "parent": layer.mesh})
                if layer.skin_name != "default":
                    data["skin"] = layer.skin_name
            else:
                data.update(
                    {
                        "type": "mesh",
                        "vertices": [
                            width / 2,
                            -height / 2,
                            -width / 2,
                            -height / 2,
                            -width / 2,
                            height / 2,
                            width / 2,
                            height / 2,
                        ],
                        "uvs": [1, 1, 0, 1, 0, 0, 1, 0],
                        "triangles": [1, 2, 3, 1, 3, 0],
                        "hull": 4,
                    }
                )
        return data

    def _write_layer_png(self, layer: LayerInfo):
        filename = (
            os.path.join(self.settings.images_dir, *layer.attachment_path.split("/"))
            + ".png"
        )
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        rect = QRect(
            layer.rect.x() - self.settings.padding,
            layer.rect.y() - self.settings.padding,
            layer.rect.width() + self.settings.padding * 2,
            layer.rect.height() + self.settings.padding * 2,
        )
        if self._write_qimage_png(layer.node, filename, rect, layer.exported_size):
            return
        export_config = self._png_config()
        if not layer.node.save(filename, 72, 72, export_config, rect):
            raise SpineExportError("Could not write PNG: {0}".format(filename))

    def _write_qimage_png(
        self, node, filename: str, rect: QRect, size: Tuple[int, int]
    ) -> bool:
        if node.colorModel() != "RGBA" or node.colorDepth() != "U8":
            return False
        raw = bytes(
            node.projectionPixelData(rect.x(), rect.y(), rect.width(), rect.height())
        )
        expected = rect.width() * rect.height() * 4
        if len(raw) < expected:
            return False
        rgba = bytearray(expected)
        rgba[0::4] = raw[2::4]
        rgba[1::4] = raw[1::4]
        rgba[2::4] = raw[0::4]
        rgba[3::4] = raw[3::4]
        image = QImage(
            bytes(rgba), rect.width(), rect.height(), _qimage_format_rgba8888()
        ).copy()
        if size != (rect.width(), rect.height()):
            image = image.scaled(
                size[0], size[1], _qt_ignore_aspect_ratio(), _qt_smooth_transformation()
            )
        return image.save(filename, "PNG")

    def _write_template_png(self):
        base = (
            self.settings.images_dir
            if self.settings.images_dir
            else os.path.dirname(self.settings.json_path)
        )
        os.makedirs(base, exist_ok=True)
        filename = os.path.join(base, "template.png")
        if not self.document.exportImage(filename, self._png_config()):
            raise SpineExportError("Could not write template PNG: {0}".format(filename))

    def _png_config(self):
        config = InfoObject()
        config.setProperty("alpha", True)
        config.setProperty("compression", 6)
        config.setProperty("forceSRGB", False)
        config.setProperty("indexed", False)
        config.setProperty("interlaced", False)
        config.setProperty("saveSRGBProfile", False)
        return config

    def _export_rect(self, layer: LayerInfo):
        trim_value = self._tag_value(
            layer.node, "trim", include_parents=layer.parent_chain, allow_empty=True
        )
        trim = (
            self.settings.trim_whitespace
            if trim_value is None
            else trim_value.lower() != "false"
        )
        if trim:
            return layer.node.bounds()
        return QRect(0, 0, self.document.width(), self.document.height())

    def _has_exportable_projection(self, node):
        try:
            bounds = node.bounds()
            return bounds is not None and bounds.width() > 0 and bounds.height() > 0
        except Exception:
            return False

    def _effective_visible(self, node, parents):
        if not node.visible():
            return False
        return all(parent.visible() for parent in parents)

    def _tags(self, name: str):
        return [
            (m.group(1).lower(), (m.group(2) or "").strip())
            for m in _TAG_RE.finditer(name or "")
        ]

    def _has_tag(self, node, tag: str):
        return any(key == tag for key, _ in self._tags(node.name()))

    def _tag_value(
        self,
        node,
        tag: str,
        include_parents: Optional[List[object]] = None,
        allow_empty: bool = False,
    ):
        nodes = list(include_parents or []) + [node]
        for current in reversed(nodes):
            is_group = current.type() == "grouplayer"
            valid = _VALID_GROUP_TAGS if is_group else _VALID_LAYER_TAGS
            for key, value in self._tags(current.name()):
                if key == tag and key in valid:
                    if value:
                        return value
                    if allow_empty:
                        return ""
                    return self._strip_tags(current.name())
        return None

    def _float_tag(self, layer: LayerInfo, tag: str, default: float):
        value = self._tag_value(layer.node, tag, include_parents=layer.parent_chain)
        if value is None:
            return default
        try:
            return float(value)
        except ValueError:
            raise SpineExportError(
                "Invalid [{0}:{1}] on {2}".format(tag, value, self._path(layer))
            )

    def _strip_tags(self, name: str):
        return _TAG_RE.sub("", name or "").strip()

    def _apply_name_patterns(self, name: str, parents: List[object]):
        result = name
        for parent in parents:
            pattern = self._tag_value(parent, "name", allow_empty=False)
            if pattern:
                if "*" not in pattern:
                    raise SpineExportError(
                        "[name:pattern] must contain '*': {0}".format(parent.name())
                    )
                result = pattern.replace("*", result)
        return result

    def _folder_path(self, nodes: List[object]):
        parts = []
        for node in nodes:
            folder = self._direct_tag_value(node, "folder")
            skin = self._direct_tag_value(node, "skin")
            value = folder if folder is not None else skin
            if not value or value == "default":
                continue
            if value.startswith("/"):
                parts = [value.strip("/")]
            else:
                parts.append(value.strip("/"))
        return "/".join(part for part in parts if part) + ("/" if parts else "")

    def _skin_name(self, nodes: List[object]):
        skin = "default"
        for node in nodes:
            value = self._direct_tag_value(node, "skin")
            if value:
                skin = value.strip("/") or self._strip_tags(node.name())
        return skin or "default"

    def _bone_name(self, nodes: List[object]):
        bone = "root"
        for node in nodes:
            value = self._direct_tag_value(node, "bone")
            if value is not None:
                bone = value or self._strip_tags(node.name())
        return bone or "root"

    def _parent_bone_name(self, parents: List[object]):
        if not parents:
            return "root"
        return self._bone_name(parents[:-1])

    def _direct_tag_value(self, node, tag: str):
        for key, value in self._tags(node.name()):
            if key == tag:
                return value or self._strip_tags(node.name())
        return None

    def _blend(self, node):
        try:
            mode = node.blendingMode()
        except Exception:
            return None
        return _BLEND_MAP.get(mode, _BLEND_MAP.get(str(mode).lower()))

    def _json_images_path(self):
        if not self.settings.images_dir:
            return ""
        if self.settings.json_path:
            try:
                rel = os.path.relpath(
                    self.settings.images_dir, os.path.dirname(self.settings.json_path)
                )
                return rel.replace(os.sep, "/") + "/"
            except ValueError:
                pass
        return self.settings.images_dir.replace(os.sep, "/") + "/"

    def _path(self, layer: LayerInfo):
        names = [parent.name() for parent in layer.parent_chain] + [layer.name]
        return "/".join(names)
