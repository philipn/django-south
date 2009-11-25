"""
Startmigration command, version 2.
"""

import sys
import os
import re
import string
import random
import inspect
import parser
from optparse import make_option

try:
    set
except NameError:
    from sets import Set as set

from django.core.management.base import BaseCommand
from django.core.management.color import no_style
from django.db import models
from django.db.models.fields.related import RECURSIVE_RELATIONSHIP_CONSTANT
from django.contrib.contenttypes.generic import GenericRelation
from django.db.models.fields import FieldDoesNotExist
from django.conf import settings

from south.migration import Migrations
from south.exceptions import NoMigrations
from south.creator import changes, actions, freezer

class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--add-model', action='append', dest='added_model_list', type='string',
            help='Generate a Create Table migration for the specified model.  Add multiple models to this migration with subsequent --model parameters.'),
        make_option('--add-field', action='append', dest='added_field_list', type='string',
            help='Generate an Add Column migration for the specified modelname.fieldname - you can use this multiple times to add more than one column.'),
        make_option('--add-index', action='append', dest='added_index_list', type='string',
            help='Generate an Add Index migration for the specified modelname.fieldname - you can use this multiple times to add more than one column.'),
        make_option('--freeze', action='append', dest='freeze_list', type='string',
            help='Freeze the specified model(s). Pass in either an app name (to freeze the whole app) or a single model, as appname.modelname.'),
        make_option('--initial', action='store_true', dest='initial', default=False,
            help='Generate the initial schema for the app.'),
        make_option('--auto', action='store_true', dest='auto', default=False,
            help='Attempt to automatically detect differences from the last migration.'),
        make_option('--stdout', action='store_true', dest='stdout', default=False,
            help='Print the migration to stdout instead of writing it to a file.'),
    )
    help = "Creates a new template migration for the given app"
    usage_str = "Usage: ./manage.py schemamigration appname migrationname [--initial] [--auto] [--add-model ModelName] [--add-field ModelName.field_name] [--stdout]"
    
    def handle(self, app=None, name="", added_model_list=None, added_field_list=None, freeze_list=None, initial=False, auto=False, stdout=False, added_index_list=None, verbosity=1, **options):
        
        # Any supposed lists that are None become empty lists
        added_model_list = added_model_list or []
        added_field_list = added_field_list or []
        added_index_list = added_index_list or []
        freeze_list = freeze_list or []

        # --stdout means name = -
        if stdout:
            name = "-"
        
        # Make sure options are compatable
        if initial and (added_model_list or added_field_list or auto):
            self.error("You cannot use --initial and other options together\n" + self.usage_str)
        
        if auto and (added_model_list or added_field_list or initial):
            self.error("You cannot use --auto and other options together\n" + self.usage_str)
        
        # specify the default name 'initial' if a name wasn't specified and we're
        # doing a migration for an entire app
        if not name and initial:
            name = 'initial'
        
        # if not name, there's an error
        if not name:
            self.error("You must provide a name for this migration\n" + self.usage_str)
        
        if not app:
            self.error("You must provide an app to create a migration for.\n" + self.usage_str)
        
        # Get the Migrations for this app (creating the migrations dir if needed)
        try:
            migrations = Migrations(app)
        except NoMigrations:
            Migrations.create_migrations_directory(app, verbose=verbosity > 0)
            migrations = Migrations(app)
        
        # See what filename is next in line. We assume they use numbers.
        highest_number = 0
        for migration in migrations:
            try:
                number = int(migration.name().split("_")[0])
                highest_number = max(highest_number, number)
            except ValueError:
                pass
        
        # Work out the new filename
        new_filename = "%04i_%s.py" % (
            highest_number + 1,
            name,
        )
        
        # What actions do we need to do?
        if auto:
            # Get the old migration
            try:
                last_migration = migrations[-1]
            except IndexError:
                self.error("You cannot use --auto on an app with no migrations. Try --initial.")
            # Make sure it has stored models
            if migrations.app_label() not in getattr(last_migration.migration_class(), "complete_apps", []):
                self.error("You cannot use automatic detection, since the previous migration does not have this whole app frozen.\nEither make migrations using '--freeze %s' or set 'SOUTH_AUTO_FREEZE_APP = True' in your settings.py." % migrations.app_label())
        elif initial:
            # Do an initial migration
            change_source = changes.InitialChanges(migrations)
        else:
            raise NotImplementedError
        
        # Get the actions, and then insert them into the actions lists
        forwards_actions = []
        backwards_actions = []
        for action_name, params in change_source.get_changes():
            # Run the correct Action class
            try:
                action_class = getattr(actions, action_name)
            except AttributeError:
                raise ValueError("Invalid action name from source: %s" % action_name)
            else:
                action = action_class(**params)
                action.add_forwards(forwards_actions)
                action.add_backwards(backwards_actions)
        
        # Work out which apps to freeze
        apps_to_freeze = []
        for to_freeze in freeze_list:
            if "." in to_freeze:
                self.error("You cannot freeze %r; you must provide an app label, like 'auth' or 'books'." % to_freeze)
            # Make sure it's a real app
            if not models.get_app(to_freeze):
                self.error("You cannot freeze %r; it's not an installed app." % to_freeze)
            # OK, it's fine
            apps_to_freeze.append(to_freeze)
        if getattr(settings, 'SOUTH_AUTO_FREEZE_APP', True):
            apps_to_freeze.append(migrations.app_label())
        
        # So, what's in this file, then?
        file_contents = MIGRATION_TEMPLATE % {
            "forwards": "\n".join(forwards_actions), 
            "backwards": "\n".join(backwards_actions), 
            "frozen_models":  freezer.freeze_apps(apps_to_freeze),
            "complete_apps": apps_to_freeze and "complete_apps = [%s]" % (", ".join(map(repr, apps_to_freeze))) or ""
        }
        
        # - is a special name which means 'print to stdout'
        if name == "-":
            print file_contents
        # Write the migration file if the name isn't -
        else:
            fp = open(os.path.join(migrations_dir, new_filename), "w")
            fp.write(file_contents)
            fp.close()
            print "Created %s." % new_filename
    
    def error(self, message, code=1):
        """
        Prints the error, and exits with the given code.
        """
        print >>sys.stderr(message)
        sys.exit(code)


MIGRATION_TEMPLATE = """# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):
    
    def forwards(self, orm):
        %(forwards)s
    
    
    def backwards(self, orm):
        %(backwards)s
    
    
    models = %(frozen_models)s
    
    %(complete_apps)s
"""