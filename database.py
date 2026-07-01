from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import uuid

db = SQLAlchemy()


def gerar_id():
    return str(uuid.uuid4())


class Atividade(db.Model):
    __tablename__ = "atividades"

    id           = db.Column(db.String(36), primary_key=True, default=gerar_id)
    titulo       = db.Column(db.String(160), nullable=False)
    descricao    = db.Column(db.String(1200), default="")
    area         = db.Column(db.String(100), default="")
    responsavel  = db.Column(db.String(100), default="")
    status       = db.Column(db.String(50), default="A fazer")
    prioridade   = db.Column(db.String(50), default="Media")
    prazo        = db.Column(db.String(10), default="")
    observacoes  = db.Column(db.String(1200), default="")
    links        = db.Column(db.Text, default="")
    criado_em    = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    concluido_em = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            "id":           self.id,
            "titulo":       self.titulo,
            "descricao":    self.descricao or "",
            "area":         self.area or "",
            "responsavel":  self.responsavel or "",
            "status":       self.status or "A fazer",
            "prioridade":   self.prioridade or "Media",
            "prazo":        self.prazo or "",
            "observacoes":  self.observacoes or "",
            "links":        self.links or "",
            "criadoEm":     self.criado_em.strftime("%Y-%m-%d") if self.criado_em else "",
            "atualizadoEm": self.atualizado_em.strftime("%Y-%m-%d") if self.atualizado_em else "",
            "concluidoEm":  self.concluido_em.strftime("%Y-%m-%d") if self.concluido_em else "",
        }


class ConfigLista(db.Model):
    __tablename__ = "config_listas"

    id    = db.Column(db.Integer, primary_key=True)
    chave = db.Column(db.String(50), unique=True, nullable=False)
    valor = db.Column(db.Text, default="")

    @staticmethod
    def get(chave, padrao=""):
        obj = ConfigLista.query.filter_by(chave=chave).first()
        return obj.valor if obj else padrao

    @staticmethod
    def set(chave, valor):
        obj = ConfigLista.query.filter_by(chave=chave).first()
        if obj:
            obj.valor = valor
        else:
            db.session.add(ConfigLista(chave=chave, valor=valor))
        db.session.commit()
