from typing import List, Any
from .unit import Unit_base
from ...storage import genid
from ...utils.readable_index import relation_index
from .entity import Entity



relation_index_counter = relation_index()

class Relationship(Unit_base):
    
    def __init__(self, relationship_tuple: List[Any] = None, text_hash_id: str = None, 
                 frozen_set: frozenset = None, context: str = None, human_readable_id: int = None):
        """
        `relationship_tuple` is expected to be a 3-item sequence of strings:
        [source, relationship, target]. In practice, upstream LLM output can
        sometimes contain `None` or non-string items, which will break when
        joined. To make the pipeline robust (especially in remote environments
        with slightly different LLM behaviour), we defensively coerce all
        elements to strings here.
        """
        if relationship_tuple:
            # Sanitize tuple elements to avoid "sequence item 0: expected str instance, NoneType found"
            cleaned_tuple: List[str] = [
                "" if v is None else str(v) for v in relationship_tuple
            ]
            # Ensure we have at least 3 elements
            if len(cleaned_tuple) < 3:
                cleaned_tuple = (cleaned_tuple + ["", "", ""])[:3]

            self.relationship_tuple = cleaned_tuple
            self.source = Entity(cleaned_tuple[0], text_hash_id)
            self.target = Entity(cleaned_tuple[2], text_hash_id)
            self.unique_relationship = frozenset((self.source.hash_id,self.target.hash_id))
            self.raw_context = " ".join(self.relationship_tuple)
            self._human_readable_id = None
            
        elif frozen_set:
            self.unique_relationship = frozenset(frozen_set)
            self.raw_context = context
            self._human_readable_id = human_readable_id
        else:
            raise ValueError("Must provide either relationship_tuple or (frozen_set and context)")
        
        self.text_hash_id = text_hash_id
        self._hash_id = None
        
        
    @property
    def hash_id(self):
        if not self._hash_id:
            self._hash_id = genid(list(self.unique_relationship),"sha256")
        return self._hash_id
    
    @property
    def human_readable_id(self):
        if not self._human_readable_id:
            self._human_readable_id = relation_index_counter.increment()
        return self._human_readable_id
    
    def __eq__(self, other):
        if isinstance(other, frozenset):
            return self.unique_relationship == other
        elif isinstance(other, Relationship):
            return self.unique_relationship == other.unique_relationship
        return False
    
    def __hash__(self):
        return hash(self.unique_relationship)
    
    def add(self, relationship_tuple: List[Any]):
        """
        Append additional raw contexts for the same logical relationship.
        As above, sanitize any None/non-string elements before joining.
        """
        cleaned_tuple: List[str] = [
            "" if v is None else str(v) for v in relationship_tuple
        ]
        raw_context = " ".join(cleaned_tuple)
        self.raw_context = self.raw_context + "\t" + raw_context

    def __str__(self):
        return self.raw_context

    @classmethod
    def from_df_row(cls,row):
        return cls(frozen_set=row['unique_relationship'],context=row['context'],human_readable_id=row['human_readable_id'])
