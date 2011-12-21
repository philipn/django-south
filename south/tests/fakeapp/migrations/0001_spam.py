from south.db import db
from django.db import models

class Migration:
    
    def forwards(self):
        # Model 'Spam'
        db.create_table("fakeapp_spam", (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('weight', models.FloatField()),
            ('expires', models.DateTimeField()),
            ('name', models.CharField(max_length=255))
        ))
    
    def backwards(self):
        db.delete_table("fakeapp_spam")


    models = {
        'fakeapp.spam': {
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'weight': ('django.db.models.fields.FloatField', [], {}),
            'expires': ('django.db.models.fields.DateTimeField', [], {}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            }
        }
