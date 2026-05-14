from .article import Article
from .law import Law, LawAttachment
from .law_reader import LawReader

# 用來聲明這個 package 對外公開哪些東西
__all__ = ["Article", "Law", "LawAttachment", "LawReader"]
