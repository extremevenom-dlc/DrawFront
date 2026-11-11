"""Thin bridge: Kotlin hands over the project as JSON, gets a .ttf file back."""
import json

import fontcore as fc


def build(project_json, out_path):
    project = fc.Project.from_dict(json.loads(project_json))
    return fc.build_font(project, out_path)["glyphs"]


def project_json_from_font(path):
    """Open a .ttf exported by DrawFont (on PC or phone) and return its drawings as project JSON."""
    return json.dumps(fc.Project.from_font(path).to_dict())
