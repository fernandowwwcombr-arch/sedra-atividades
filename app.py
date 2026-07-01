"""
=============================================================
  SEDRA — Controle de Atividades
  Versão: V1.0
=============================================================
"""

import os
from flask import Flask, render_template, request, jsonify
from database import db, Atividade, ConfigLista
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "sedra-atividades-chave-2026")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

_db_url = os.environ.get("DATABASE_URL", "")
if _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = (
    _db_url or "sqlite:///" + os.path.join(BASE_DIR, "instance", "atividades.db")
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)

db.init_app(app)

STATUSES   = ["A fazer", "Em andamento", "Aguardando", "Concluido"]
PRIORITIES = ["Baixa", "Media", "Alta", "Urgente"]
DEFAULT_AREAS   = ["Administrativo", "Comercial", "Compras", "Financeiro", "Operacao", "Projetos"]
DEFAULT_OWNERS  = ["Sedra"]


def get_lists():
    areas = ConfigLista.get("areas", "\n".join(DEFAULT_AREAS)).splitlines()
    owners = ConfigLista.get("responsaveis", "\n".join(DEFAULT_OWNERS)).splitlines()
    # enriquecer com valores já usados nas atividades
    used_areas  = [a.area for a in Atividade.query.with_entities(Atividade.area).distinct() if a.area]
    used_owners = [a.responsavel for a in Atividade.query.with_entities(Atividade.responsavel).distinct() if a.responsavel]
    all_areas  = sorted(set(filter(None, areas + used_areas)))
    all_owners = sorted(set(filter(None, owners + used_owners)))
    return {"areas": all_areas, "responsaveis": all_owners}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/dados")
def api_dados():
    atividades = (Atividade.query
                  .order_by(Atividade.criado_em.desc())
                  .all())
    return jsonify({
        "ok": True,
        "tasks": [a.to_dict() for a in atividades],
        "settings": {"statuses": STATUSES, "priorities": PRIORITIES},
        "lists": get_lists(),
        "logoUrl": ConfigLista.get("logo_url", ""),
    })


@app.route("/api/atividade", methods=["POST"])
def api_salvar():
    data = request.get_json() or {}
    titulo = (data.get("titulo") or "").strip()
    if not titulo:
        return jsonify({"ok": False, "erro": "Informe o titulo da atividade."}), 400

    ativ_id = (data.get("id") or "").strip()
    if ativ_id:
        ativ = Atividade.query.get(ativ_id)
        if not ativ:
            return jsonify({"ok": False, "erro": "Atividade nao encontrada."}), 404
    else:
        ativ = Atividade()
        db.session.add(ativ)

    novo_status = data.get("status", "A fazer")
    if novo_status not in STATUSES:
        novo_status = STATUSES[0]

    ativ.titulo      = titulo
    ativ.descricao   = (data.get("descricao") or "").strip()
    ativ.area        = (data.get("area") or "").strip()
    ativ.responsavel = (data.get("responsavel") or "").strip()
    ativ.status      = novo_status
    ativ.prioridade  = data.get("prioridade", "Media") if data.get("prioridade") in PRIORITIES else "Media"
    ativ.prazo       = (data.get("prazo") or "")[:10]
    ativ.observacoes = (data.get("observacoes") or "").strip()
    ativ.links       = (data.get("links") or "").strip()
    ativ.atualizado_em = datetime.utcnow()

    if novo_status == "Concluido" and not ativ.concluido_em:
        ativ.concluido_em = datetime.utcnow()
    elif novo_status != "Concluido":
        ativ.concluido_em = None

    db.session.commit()
    return jsonify({"ok": True, "task": ativ.to_dict()})


@app.route("/api/atividade/<ativ_id>/status", methods=["PUT"])
def api_status(ativ_id):
    ativ = Atividade.query.get(ativ_id)
    if not ativ:
        return jsonify({"ok": False, "erro": "Atividade nao encontrada."}), 404

    novo_status = (request.get_json() or {}).get("status", "")
    if novo_status not in STATUSES:
        return jsonify({"ok": False, "erro": "Status invalido."}), 400

    ativ.status = novo_status
    ativ.atualizado_em = datetime.utcnow()
    if novo_status == "Concluido" and not ativ.concluido_em:
        ativ.concluido_em = datetime.utcnow()
    elif novo_status != "Concluido":
        ativ.concluido_em = None

    db.session.commit()
    return jsonify({"ok": True, "task": ativ.to_dict()})


@app.route("/api/atividade/<ativ_id>", methods=["DELETE"])
def api_deletar(ativ_id):
    ativ = Atividade.query.get(ativ_id)
    if not ativ:
        return jsonify({"ok": False, "erro": "Atividade nao encontrada."}), 404
    db.session.delete(ativ)
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/api/listas", methods=["POST"])
def api_listas():
    data = request.get_json() or {}
    areas  = [a.strip() for a in (data.get("areas") or []) if a.strip()]
    owners = [o.strip() for o in (data.get("responsaveis") or []) if o.strip()]
    logo   = (data.get("logoUrl") or "").strip()

    ConfigLista.set("areas", "\n".join(sorted(set(areas))))
    ConfigLista.set("responsaveis", "\n".join(sorted(set(owners))))
    if logo:
        ConfigLista.set("logo_url", logo)

    return jsonify({"ok": True, "lists": get_lists(), "logoUrl": ConfigLista.get("logo_url", "")})


# ── Inicialização ──────────────────────────────────────────────
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    print("=" * 50)
    print("  SEDRA Atividades — V1.0")
    print("  Acesse: http://localhost:5001")
    print("=" * 50)
    app.run(debug=True, host="0.0.0.0", port=5001)
