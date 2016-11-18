Overview
=========



`nosql` is a schemaless ORM for relational db backed by SQLAlchemy.

It's ultermately an implementation of the schemaless ORM introduced by Bret Taylor.

http://backchannel.org/blog/friendfeed-schemaless-mysql

Installation
=========
```bash
pip install nosql
```

Test
=========
```bash
python setup.py test
```

Usage
=========
No instruction is better than real code! Say you are building a `Flask` app.

```python
import nosql
from app import db


class User(nosql.SchemalessModel):
	engine = db.engine
	indexes = (
		('email',),
		('facebook_id',),
		('city',)
	)

	
User.create_all()

user = User()
user.email = 'xxx@gmail.com'
user.name = 'xx xx'
user.save()


# find returns a generator
>>> [user.name for user in User.find()]
['xx xx']


# find_one returns an instance, support any attribute
>>> User.find_one(email='xxx@gmail.com').name
xx xx


# added_id & id is auto-generated
>>> user.id
e597bb954cf74d51937d5a5e9fd2f2b8

>>> user.added_id
1


# retrieve non-exist attr returns None
>>> user.idol


>>> user.delete()

>>> list(User.find())
[]
```


Index
=========
Because `nosql` creates index tables, querying random attribute is fast.

Some todo's for index

* `index_updater` allows indexes to be added later on and schedule data pushing in the background.
* `sharding` on index.


License
=========
MIT
