import pickle
import uuid

from sqlalchemy import schema, types, dialects
from sqlalchemy.sql import insert, update, delete, select, join, and_, func


class SchemalessModel(object):
    @classmethod
    def _get_largest_index(cls, fields):
        field_set = set(fields)
        indexes = [(set(index), index) for index in cls.indexes]
        
        coverage = [(len(field_set-index[0]), index[1]) for index in indexes if field_set >= index[0]]
        
        if not coverage: return []
        return min(coverage)[1]
    
    @classmethod
    def _unmarshal(cls, added_id, id, attrs):
        instance = cls.__new__(cls)
        instance.__init__()
        instance.added_id = added_id
        instance.id = id
        instance.__dict__.update(attrs)
        return instance
        
    @classmethod
    def _find_index_table(cls, name=None):
        if name is None:
            raise ValueError('index table name is not provided.')
        try:
            table = filter(lambda x: x.name == name, cls.index_tables)[0]
        except IndexError:
            raise RuntimeError('cannot find index table %s.' % name)
        return table
        
    @classmethod
    def _find_index(cls, index_table):
        for index in cls.indexes:
            if index_table.name == '%s_%s' % (cls.table.name, '_'.join(index)):
                return index
        raise RuntimeError('cannot find index by table name %s.' % index_table.name)
        
    @classmethod
    def find_one(cls, **params):
        iterator = cls.find(**params)
        try:
            item = iterator.next()
        except StopIteration:
            item = None
        return item
        
    @classmethod
    def find(cls, **params):
        if 'added_id' in params:
            for added_id, id, data in select([cls.table], cls.table.c.added_id == params['added_id']).execute():
                loaded_dict = pickle.loads(data.encode('utf-8'))
                yield cls._unmarshal(added_id, id, loaded_dict)
        else:
            if not any(params):
                params = {}
                index = []
            elif 'id' in params:
                index = ['id']
            else:
                index = cls._get_largest_index(params.keys())
        
            if not index:
                stmt = select([cls.table])
            elif index == ['id']:
                stmt = select([cls.table], cls.table.c.id == params['id'])
                del params['id']
            else:
                index_table = cls._find_index_table('%s_%s' % (cls.table.name, '_'.join(index)))
                columns = filter(lambda col: col.name in index, index_table.c)
                clauses = [col == value for col, value in zip(columns, [params[i] for i in index])]
            
                stmt = join(cls.table, index_table, cls.table.c.id == index_table.c.id).\
                        select(and_(*clauses))
                for field in index:
                    del params[field]
            
            query = stmt.execute()
        
            for row in query:
                added_id, id, data = row[:3]
                loaded_dict = pickle.loads(data.encode('utf-8'))
        
                if params:
                    if all(loaded_dict.get(field, None) == params[field] for field in params):
                        yield cls._unmarshal(added_id, id, loaded_dict)
                else:
                    yield cls._unmarshal(added_id, id, loaded_dict)
                
    @classmethod
    def create_all(cls):
        if not hasattr(cls, 'engine') or not hasattr(cls, 'indexes'):
            raise ValueError('cannot initialize %s without specific engine and indexes.' % cls.__name__)

        table_name = cls.__name__.lower()
        metadata = schema.MetaData()
        metadata.bind = cls.engine
        
        # create basic table
        BLOB = dialects.postgresql.BYTEA if str(cls.engine.url).find('postgres') != -1 else types.BLOB
        
        table = schema.Table(table_name, metadata,
            schema.Column('added_id', types.Integer, primary_key=True),
            schema.Column('id', types.Text, index=True, nullable=False),
            schema.Column('data', BLOB, nullable=False)
        )
        table.create(cls.engine, checkfirst=True)
        cls.table = table
        
        # create index tables
        cls.index_tables = []
        for index in cls.indexes:
            columns = [schema.Column('id', types.Text, nullable=False, primary_key=True)]
            for col in index:
                columns.append(schema.Column(col, types.Text, primary_key=True))
            index_table_name = '%s_%s' % (table_name, '_'.join(index))
            index_table = schema.Table(index_table_name, metadata, *columns)
            index_table.create(cls.engine, checkfirst=True)
            cls.index_tables.append(index_table)
            
    @classmethod
    def drop_all(cls):
        cls.table.drop(cls.engine)
        for index_table in cls.index_tables:
            index_table.drop(cls.engine)
        
    def __init__(self, **kwargs):
        self.added_id = None
        self.id = uuid.uuid4().hex
        self.__dict__.update(kwargs)
        
    def __getattr__(self, name):
        return self.__dict__.get(name, None)
        
    def __eq__(self, other):
        if not hasattr(self, 'id') or not hasattr(other, 'id'):
            return False
        return self.id == other.id
        
    def _populate_index(self, index_table, fields):
        values = []
        for field in fields:
            if field not in self.__dict__:
                return
            values.append(getattr(self, field) or '')
        
        values = zip(fields, values)
        values.insert(0, ('id', self.id))
        values = dict(values)
        
        index = list(self.__class__._find_index(index_table))
        index.insert(0, 'id')
        columns = filter(lambda col: col.name in index, index_table.c)
        clauses = [col == value for col, value in zip(columns, [values[i] for i in index])]
    
        query = select([func.count(index_table.c.id)]).where(and_(*clauses)).scalar()
                
        if query:
            update(index_table).where(index_table.c.id == self.id).values(**values).execute()
        else:
            insert(index_table, values=values).execute()
        
    def save(self):
        cls = self.__class__
        
        added_id = self.added_id
        del self.__dict__['added_id']
        
        if added_id is not None:
            stmt = update(cls.table).where(cls.table.c.added_id == added_id).\
                    values(id=self.id, data=pickle.dumps(self.__dict__))
            stmt.execute()
            self.added_id = added_id
        else:
            stmt = insert(cls.table, values=dict(id=self.id, data=pickle.dumps(self.__dict__)))
            result = stmt.execute()
            self.added_id = result.inserted_primary_key[0]
            
        for index_table, fields in zip(cls.index_tables, cls.indexes):
            self._populate_index(index_table, fields)
            
    def delete(self):
        cls = self.__class__
        
        if self.added_id:
            stmt = delete(cls.table).where(cls.table.c.added_id == self.added_id)
        elif self.id:
            stmt = delete(cls.table).where(cls.table.c.id == self.id)
        else:
            raise RuntimeError('cannot delete instance from database.')
        stmt.execute()
            
        for index_table in cls.index_tables:
            delete(index_table).where(index_table.c.id == self.id).execute()