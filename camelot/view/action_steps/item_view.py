#  ============================================================================
#
#  Copyright (C) 2007-2013 Conceptive Engineering bvba. All rights reserved.
#  www.conceptive.be / info@conceptive.be
#
#  This file is part of the Camelot Library.
#
#  This file may be used under the terms of the GNU General Public
#  License version 2.0 as published by the Free Software Foundation
#  and appearing in the file license.txt included in the packaging of
#  this file.  Please review this information to ensure GNU
#  General Public Licensing requirements will be met.
#
#  If you are unsure which license is appropriate for your use, please
#  visit www.python-camelot.com or contact info@conceptive.be
#
#  This file is provided AS IS with NO WARRANTY OF ANY KIND, INCLUDING THE
#  WARRANTY OF DESIGN, MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE.
#
#  For use of this library in commercial applications, please contact
#  info@conceptive.be
#
#  ============================================================================

"""
Various ``ActionStep`` subclasses that manipulate the `item_view` of 
the `ListActionGuiContext`.
"""

from sqlalchemy.orm import Query

from PyQt4.QtCore import Qt

from camelot.admin.action.base import ActionStep
from camelot.view.proxy.collection_proxy import CollectionProxy
from camelot.view.proxy.queryproxy import QueryTableProxy


class Sort( ActionStep ):
    
    def __init__( self, column, order = Qt.AscendingOrder ):
        """Sort the items in the item view ( list, table or tree )
        
        :param column: the index of the column on which to sort
        :param order: a :class:`Qt.SortOrder`
        """
        self.column = column
        self.order = order
        
    def gui_run( self, gui_context ):
        if gui_context.item_view != None:
            model = gui_context.item_view.model()
            model.sort( self.column, self.order )

class OpenTableView( ActionStep ):
    """Open a new table view in the workspace.
    
    :param admin: an `camelot.admin.object_admin.ObjectAdmin` instance
    :param value: a list of objects or a query

    .. attribute:: title
        the title of the the new view
        
    .. attribute:: subclasses
        a tree of subclasses to be displayed on the left of the

    .. attribute:: new_tab
        open the view in a new tab instead of the current tab
        
    """
    
    def __init__( self, admin, value ):
        self.admin = admin
        self.value = value
        self.new_tab = False
        self.title = admin.get_verbose_name_plural()
        self.subclasses = admin.get_subclass_tree()
        self.search_text = ''
        if isinstance(value, list):
            self.proxy = CollectionProxy
        elif isinstance(value, Query):
            self.proxy = QueryTableProxy
        else:
            raise Exception('Unhandled value type : {0}'.format(type(value)))
        self.filters = admin.get_filters()
        self.list_actions = admin.get_list_actions()
        self.columns = self.admin.get_columns()
        self.static_fa = list(self.admin.get_static_field_attributes([c[0] for c in self.columns]))
    
    def gui_run( self, gui_context ):
        from camelot.view.controls.tableview import TableView
        table_view = TableView(gui_context, 
                               self.admin, 
                               self.search_text,
                               proxy = self.proxy)
        table_view.set_admin(self.admin)
        table_view.set_subclass_tree(self.subclasses)
        if self.new_tab == True:
            gui_context.workspace.add_view(table_view)
        else:
            gui_context.workspace.set_view(table_view)
        table_view.change_title(self.title)
        # columns and static_fa should be reworked
        model = table_view.get_model()
        print 'columns', self.columns
        print 'static fa', self.static_fa
        model.set_columns_and_static_field_attributes((self.columns, self.static_fa))
        print '================='
        print model
        print model._columns
        # filters can have default values, so they need to be set before
        # the value is set
        #table_view.set_filters(self.filters)
        print 'set value', self.value
        table_view.set_value(self.value)
        #table_view.set_list_actions(self.list_actions)
        print 'after set value'
        print model._columns
        table_view.setFocus(Qt.PopupFocusReason)

