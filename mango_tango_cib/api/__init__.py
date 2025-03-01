from flask import Flask
from flask.views import MethodView
from flask_smorest import Api, Blueprint
from marshmallow import Schema, fields as ma_fields
from marshmallow_dataclass import class_schema
from dataclasses import dataclass
from typing import Any
from pathlib import Path
import json

config_file = Path("~/.config/mango_tango_cib/config.json").expanduser()


def parse_json_file(file_path: Path) -> Any | None:
    if not file_path.exists():
        return None

    text = file_path.read_text()
    return json.loads(text) if text else None


config = parse_json_file(config_file) or {}


data_dir = Path(config.get("data_dir", "~/.mango_tango_cib/data")).expanduser()
print(data_dir)


@dataclass
class Project:
    name: str
    directory_name: str

    directory_path: Path


app = Flask(__name__)
app.config["API_TITLE"] = "My API"
app.config["API_VERSION"] = "v1"
app.config["OPENAPI_VERSION"] = "3.0.2"

app.config["OPENAPI_URL_PREFIX"] = "/docs"
app.config["OPENAPI_SWAGGER_UI_PATH"] = "/swagger"
app.config["OPENAPI_SWAGGER_UI_URL"] = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"
app.config["OPENAPI_SWAGGER_UI_CONFIG"] = {
    "persistAuthorization": True,
}


def get_projects(project_dir: Path) -> list[Project]:
    if not project_dir.exists():
        return []

    return [
        p
        for x in project_dir.iterdir()
        if x.is_dir() and (p := get_project(project_dir, x.name)) is not None
    ]


def get_project(project_dir: Path, project_name: str) -> Project | None:
    project_path = project_dir / project_name
    if not project_path.exists():
        return None

    project_config = parse_json_file(project_path / "config.json")
    if not project_config:
        return None

    return Project(
        name=project_config.get("name"),
        directory_name=project_name,
        directory_path=project_path,
    )


class ProjectSchema(Schema):
    name = ma_fields.String()
    directory_name = ma_fields.String()


blp = Blueprint(
    "projects",
    "projects",
    url_prefix="/api/projects",
    description="Operations on projects",
)


@blp.route("")
class ProjectsView(MethodView):
    @blp.response(200, ProjectSchema(many=True))
    def get(self):
        return get_projects(data_dir)


@blp.route("/<string:project_name>")
class ProjectView(MethodView):
    @blp.response(200, ProjectSchema)
    def get(self, project_name):
        # TODO -- get project by name

        return None

    @blp.response(201, ProjectSchema)
    @blp.arguments(ProjectSchema(only=("name",)))
    def post(self, project, project_name: str):
        project_dir = data_dir / project_name
        if project_dir.exists():
            return "Project already exists", 400

        project_dir.mkdir(parents=True)
        project_json = project_dir / "config.json"
        project_json.write_text(json.dumps(project))
        return get_project(data_dir, project_name)


api = Api(app)
api.register_blueprint(blp)

for x in app.url_map.iter_rules():
    print(x)

if __name__ == "__main__":
    app.run(debug=True)
