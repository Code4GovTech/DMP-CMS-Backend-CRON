from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func,BigInteger
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base


Base = declarative_base()



# Define your models
class DmpIssue(Base):
    __tablename__ = 'dmp_issues'

    id = Column(Integer, primary_key=True, autoincrement=True)
    issue_url = Column(String, nullable=False)
    issue_number = Column(Integer, nullable=False)
    mentor_username = Column(String, nullable=True)
    contributor_username = Column(String, nullable=True)
    title = Column(String, nullable=False)
    org_id = Column(Integer, ForeignKey('dmp_orgs.id'), nullable=False)
    description = Column(Text, nullable=True)
    repo = Column(String, nullable=True)

    def __repr__(self):
        return f"<DmpIssue(id={self.id}, title={self.title})>"

    def to_dict(self):
        return {
            'id': self.id,
            'issue_url': self.issue_url,
            'issue_number': self.issue_number,
            'mentor_username': self.mentor_username,
            'contributor_username': self.contributor_username,
            'title': self.title,
            'org_id': self.org_id,
            'description': self.description,
            'repo': self.repo
        }

class DmpOrg(Base):
    __tablename__ = 'dmp_orgs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    link = Column(String, nullable=False)
    repo_owner = Column(String, nullable=False)
    dmp_issues = relationship('DmpIssue', backref='organization', lazy=True)

    def __repr__(self):
        return f"<DmpOrg(id={self.id}, name={self.name})>"

    def to_dict(self):
        return {
            'id': self.id,
            'created_at': self.created_at.isoformat(),
            'name': self.name,
            'description': self.description,
            'link': self.link,
            'repo_owner': self.repo_owner
        }


class DmpIssueUpdate(Base):
    __tablename__ = 'dmp_issue_updates'

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    body_text = Column(Text, nullable=False)
    comment_link = Column(String, nullable=False)
    comment_id = Column(BigInteger, primary_key=True, nullable=False)
    comment_api = Column(String, nullable=False)
    comment_updated_at = Column(DateTime, nullable=False)
    dmp_id = Column(Integer, ForeignKey('dmp_orgs.id'), nullable=False)
    created_by = Column(String, nullable=False)

    def __repr__(self):
        return f"<DmpIssueUpdate(comment_id={self.comment_id}, dmp_id={self.dmp_id})>"

    def to_dict(self):
        return {
            'created_at': self.created_at.isoformat(),
            'body_text': self.body_text,
            'comment_link': self.comment_link,
            'comment_id': self.comment_id,
            'comment_api': self.comment_api,
            'comment_updated_at': self.comment_updated_at.isoformat(),
            'dmp_id': self.dmp_id,
            'created_by': self.created_by
        }

class Prupdates(Base):
    __tablename__ = 'dmp_pr_updates'

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    pr_id = Column(Integer, nullable=False, primary_key=True)
    status = Column(String, nullable=False)
    title = Column(String, nullable=False)
    pr_updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    merged_at = Column(DateTime)
    closed_at = Column(DateTime)
    dmp_id = Column(Integer, ForeignKey('dmp_issues.id'), nullable=False)
    link = Column(String, nullable=False)

    def __repr__(self):
        return f'<PullRequest {self.pr_id} - {self.title}>'

    def to_dict(self):
        return {
            'created_at': self.created_at.isoformat(),
            'pr_id': self.pr_id,
            'status': self.status,
            'title': self.title,
            'pr_updated_at': self.pr_updated_at.isoformat(),
            'merged_at': self.merged_at.isoformat() if self.merged_at else None,
            'closed_at': self.closed_at.isoformat() if self.closed_at else None,
            'dmp_id': self.dmp_id,
            'link': self.link
        }

class DmpWeekUpdate(Base):
    __tablename__ = 'dmp_week_updates'

    id = Column(Integer, primary_key=True, autoincrement=True)
    issue_url = Column(String, nullable=False)
    week = Column(Integer, nullable=False)
    total_task = Column(Integer, nullable=False)
    completed_task = Column(Integer, nullable=False)
    progress = Column(Integer, nullable=False)
    task_data = Column(Text, nullable=False)
    dmp_id = Column(Integer, nullable=False)

    def __repr__(self):
        return f"<DmpWeekUpdate(id={self.id}, week={self.week}, dmp_id={self.dmp_id})>"
    
    def to_dict(self):
        return {
            'id': self.id,
            'week': self.week,
            'dmp_id': self.dmp_id,
        }
