#  ============================================================================
#
#  Copyright (C) 2007-2016 Conceptive Engineering bvba.
#  www.conceptive.be / info@conceptive.be
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are met:
#      * Redistributions of source code must retain the above copyright
#        notice, this list of conditions and the following disclaimer.
#      * Redistributions in binary form must reproduce the above copyright
#        notice, this list of conditions and the following disclaimer in the
#        documentation and/or other materials provided with the distribution.
#      * Neither the name of Conceptive Engineering nor the
#        names of its contributors may be used to endorse or promote products
#        derived from this software without specific prior written permission.
#  
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
#  ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
#  WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#  DISCLAIMED. IN NO EVENT SHALL <COPYRIGHT HOLDER> BE LIABLE FOR ANY
#  DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
#  (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
#  LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
#  ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
#  (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
#  SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
#  ============================================================================

"""Classes to layout fields on a form.  These are mostly used for specifying the
form_display attribute in Admin classes, but they can be used on their own as
well.  Form classes can be used recursive.
"""
import dataclasses
import json
import logging
from typing import Iterable, Any

from dataclasses import dataclass, field, InitVar

from ..core.serializable import Serializable, ObjectDataclassSerializable

logger = logging.getLogger('camelot.view.forms')

from ..core.qt import QtCore, QtWidgets, variant_to_py
from ..core.exception import log_programming_error

class MetaForm(type):
    forms = dict()

    def __new__(cls, clsname, bases, attrs):
        newclass = super().__new__(cls, clsname, bases, attrs)
        if issubclass(newclass, (Serializable,)):
            cls.forms[clsname] = newclass
        return newclass

@dataclass
class AbstractForm(ObjectDataclassSerializable, metaclass=MetaForm):
    """
    Base Form class to put fields on a form.  The base class of a form is
    a list.  So the form itself is nothing more than a list of field names or
    sub-forms.  A form can thus be manipulated using the list's method such as
    append or insert.
        
    A form can be converted to a `Qt` widget by calling its `render` method.
    
    Forms are defined using the `form_display` attribute of an `Admin` class::
    
        class Admin( EntityAdmin ):
            form_display = Form( [ 'title', 'short_description', 
                                   'release_date' ] )
                                   
    and takes these parameters :
    
        :param content: an iterable with field names or sub-forms to render
        :param columns: the number of columns in which to order the fields.
    
    .. image:: /_static/form/form.png
    
    """
    title: str = field(init=False)
    content: list = field(init=False)
    scrollbars: bool = field(init=False, default=False)
    columns: int = field(init=False, default=1)
    
    @classmethod
    def get_content_fields(cls, content):
        """:return: the fields, visible in this form"""
        return [field for field in cls._get_fields_from_form(content)]

    def get_fields(self):
        """:return: the fields, visible in this form"""
        return [field for field in self._get_fields_from_form()]

    def _get_fields_from_form(self):
        for field in self.content:
            if field is None:
                continue
            elif issubclass(type(field), AbstractForm):
                for nested_field in field._get_fields_from_form():
                    yield nested_field
            else:
                assert isinstance(field, str) or (field is None)
                yield field

    def remove_field(self, original_field):
        """Remove a field from the form, This function can be used to modify
        inherited forms.

        :param original_field: the name of the field to be removed
        :return: `True` if the field was found and removed
        """
        for c in self.content:
            if issubclass(type(c), AbstractForm):
                c.remove_field(original_field)
            if original_field in self.content:
                self.content.remove(original_field)
                return True
        return False

    def replace_field(self, original_field, new_field):
        """Replace a field on this form with another field.  This function can be used to
        modify inherited forms.

        :param original_field : the name of the field to be replace
        :param new_field : the name of the new field
        :return: `True` if the original field was found and replaced
        """
        for i, c in enumerate(self.content):
            if issubclass(type(c), AbstractForm):
                c.replace_field(original_field, new_field)
            elif c == original_field:
                self.content[i] = new_field
                return True
        return False

    def add_field(self, new_field):
        self.content.append(new_field)
    
    def __str__(self):
        return 'AbstractForm(%s)' % (u','.join(str(c) for c in self.content))  
    
    @classmethod
    def render(cls, widgets, form, parent=None, toplevel=False):
        """
        :param widgets: a :class:`camelot.view.controls.formview.FormEditors` object
            that is able to create the widgets for this form
        :param form: the serialized form data
        :param parent: the :class:`QtWidgets.QWidget` in which the form is placed
        :param toplevel: a :keyword:`boolean` indicating if this form is toplevel,
            or a child form of another form.  A toplevel form will be expanding,
            while a non toplevel form is only expanding if it contains other
            expanding elements.
        :return: a :class:`QtWidgets.QWidget` into which the form is rendered
        """
        if isinstance(form, bytes):
            form = json.loads(form)
        if isinstance(form, list):
            form = form[1]
        
        logger.debug('rendering %s' % cls.__name__)
        from camelot.view.controls.editors.wideeditor import WideEditor
        form_widget = QtWidgets.QWidget(parent)
        form_layout = QtWidgets.QGridLayout()
        
        # where 1 column in the form is a label and a field, so two columns in the grid
        columns = min(form["columns"], len(form["content"]))
        # make sure all columns have the same width
        for i in range(columns * 2):
            if i % 2:
                form_layout.setColumnStretch(i, 1)

        row_span = 1

        class cursor(object):

            def __init__(self):
                self.row = 0
                self.col = 0

            def next_row(self):
                self.row = self.row + 1
                self.col = 0

            def next_col(self):
                self.col = self.col + 2
                if self.col >= columns * 2:
                    self.next_row()

            def next_empty_row(self):
                if self.col != 0:
                    self.next_row()

            def __str__(self):
                return '%s,%s' % (self.row, self.col)

        c = cursor()

        has_vertical_expanding_row = False
        for field in form["content"]:
            size_policy = None
            if field is None:
                c.next_col()
            elif isinstance(field, list):
                field_class = MetaForm.forms.get(field[0])
                if issubclass(field_class, AbstractForm):
                    c.next_empty_row()
                    col_span = 2 * columns
                    f = field_class.render(widgets, field[1], parent, False)
                    if isinstance(f, QtWidgets.QLayout):
                        #
                        # this should maybe be recursive ??
                        #
                        for layout_item_index in range(f.count()):
                            layout_item = f.itemAt(layout_item_index)
                            layout_item_widget = layout_item.widget()
                            if layout_item_widget and layout_item_widget.sizePolicy().verticalPolicy() == QtWidgets.QSizePolicy.Expanding:
                                has_vertical_expanding_row = True
                        form_layout.addLayout(f, c.row, c.col, row_span, col_span)
                    elif isinstance(f, QtWidgets.QLayoutItem):
                        form_layout.addItem(f)
                    else:
                        form_layout.addWidget(f, c.row, c.col, row_span, col_span)
                        size_policy = f.sizePolicy()
                    c.next_row()
            else:
                editor = widgets.create_editor(field, form_widget)
                if editor is not None:
                    if isinstance(editor, WideEditor):
                        c.next_empty_row()
                        col_span = 2 * columns
                        label = widgets.create_label(field, editor, form_widget)
                        if label is not None:
                            form_layout.addWidget(label, c.row, c.col, row_span, col_span)
                            c.next_row()
                        form_layout.addWidget(editor, c.row, c.col, row_span, col_span)
                        stretch = variant_to_py(editor.property('stretch'))
                        if stretch is not None:
                            form_layout.setRowStretch(c.row, stretch)
                        c.next_row()
                    else:
                        col_span = 1
                        label = widgets.create_label(field, editor, form_widget)
                        if label is not None:
                            form_layout.addWidget(label, c.row, c.col, row_span, col_span)
                        form_layout.addWidget(editor, c.row, c.col + 1, row_span, col_span)
                        c.next_col()
                    size_policy = editor.sizePolicy()
                else:
                    log_programming_error(logger, 'widgets should contain a widget for field %s' % str(field))
            if size_policy and size_policy.verticalPolicy() == QtWidgets.QSizePolicy.Expanding:
                has_vertical_expanding_row = True

        if (not has_vertical_expanding_row) and toplevel and form_layout.rowCount():
            form_layout.setRowStretch(form_layout.rowCount(), 1)

        # fix embedded forms
        if not toplevel:
            form_layout.setContentsMargins(0, 0, 0, 0)

        if toplevel or has_vertical_expanding_row:
            form_widget.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                                      QtWidgets.QSizePolicy.Expanding)
        form_widget.setLayout(form_layout)

        if form["scrollbars"]:
            scroll_area = QtWidgets.QScrollArea(parent)
            # we should inherit parent's background color
            scroll_area.setWidget(form_widget)
            scroll_area.setWidgetResizable(True)
            scroll_area.setFrameStyle(QtWidgets.QFrame.NoFrame)
            return scroll_area

        logger.debug('end rendering %s' % cls.__name__)

        return form_widget

@dataclass
class Form(AbstractForm):
    title: str = field(init=False, default=None)
    content: list
    scrollbars: bool = False
    columns: int = 1

@dataclass
class Break(AbstractForm):
    """End a line in a multi-column form"""

    title: str = field(init=False, default=None)    
    content: list = field(init=False, default_factory=list)

@dataclass
class Label(AbstractForm):
    """Render a label using a :class:`QtWidgets.QLabel`
            :param label : string to be displayed in the label
            :param alignment : alignment of text in the label. values that make
                sense 'left', 'right' or 'center'
            :param style : string of cascading stylesheet instructions
    """

    title: str = field(init=False, default=None)
    content: list = field(init=False, default_factory=list)
    label: str
    alignment: str = 'left'
    style: str = None

    @classmethod
    def render(cls, widgets, form, parent=None, toplevel=False):
        if isinstance(form, bytes):
            form = json.loads(form)
        if isinstance(form, list):
            form = form[1]

        if form["style"]:
            widget = QtWidgets.QLabel('<p align="%s" style="%s">%s</p>' % (form["alignment"], form["style"], str(form["label"])))
        else:
            widget = QtWidgets.QLabel('<p align="%s">%s</p>' % (form["alignment"], str(form["label"])))
        widget.setSizePolicy(QtWidgets.QSizePolicy.Preferred,
                             QtWidgets.QSizePolicy.Fixed)
        return widget

class DelayedTabWidget(QtWidgets.QTabWidget):
    """Helper class for :class:`TabForm` to delay the creation of tabs to
the moment the tab is shown.
    """

    def __init__(self, widgets, tabs, parent=None):
        super(DelayedTabWidget, self).__init__(parent)
        self._widgets = widgets
        self._forms = []
        #
        # keep track for each of the tabs wether they are expanding,
        #
        self._vertical_expanding = [False] * len(tabs)
        #
        # set dummy tab widgets
        #
        for tab_label, tab_form in tabs:
            self._forms.append(tab_form)
            tab_widget = QtWidgets.QWidget(self)
            self.addTab(tab_widget, str(tab_label))
        #
        # render the first tab and continue rendering until we have
        # a tab with an expanding size policy, because then we know
        # the widget itself should be expanding, and we can delay
        # the rendering of the other tabs
        #
        for i in range(len(tabs)):
            self.render_tab(i)
            if sum(self._vertical_expanding):
                self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
                #
                # if one of the tabs is expanding, the others should have spacer
                # items to stretch
                #
                for j, vertical_expanding_of_widget in zip(list(range(i)), self._vertical_expanding):
                    if vertical_expanding_of_widget == False:
                        tab_widget = self.widget(j)
                        tab_widget.layout().addStretch(1)
                break
        self.currentChanged.connect(self.render_tab)

    @QtCore.qt_slot(int)
    def render_tab(self, index):
        """
        Render the tab at index
        """
        tab_widget = self.widget(index)
        layout = tab_widget.layout()
        if layout != None:
            # this tab has been rendered before
            return
        layout = QtWidgets.QVBoxLayout(tab_widget)
        tab_form = self._forms[index]
        form_class = MetaForm.forms.get(tab_form[0])
        tab_form_widget = form_class.render(self._widgets, tab_form[1], toplevel=False)
        layout.addWidget(tab_form_widget)
        tab_widget.setLayout(layout)
        size_policy = tab_form_widget.sizePolicy()
        if size_policy.verticalPolicy() == QtWidgets.QSizePolicy.Expanding:
            self._vertical_expanding[index] = True
        else:
            self._vertical_expanding[index] = False
        #
        # if other widgets are expanding, and this one isn't, add some stretch
        #
        if self._vertical_expanding[index] == False and sum(self._vertical_expanding):
            tab_widget.layout().addStretch(1)

@dataclass
class TabForm(AbstractForm):
    """
    Render forms within a :class:`QtWidgets.QTabWidget`::
    
        from = TabForm([('First tab', ['title', 'short_description']),
                        ('Second tab', ['director', 'release_date'])])
    
    .. image:: /_static/form/tab_form.png
    
    :param tabs: a list of tuples of (tab_label, tab_form)
    :param position: the position of the tabs with respect to the pages
    """

    NORTH = 'North'
    SOUTH = 'South'
    WEST = 'West'
    EAST = 'East'

    title: str = field(init=False, default=None)
    tabs: InitVar[list]
    position: str = NORTH

    def __post_init__(self, tabs):
        assert isinstance(tabs, list)
        assert self.position in [self.NORTH, self.SOUTH, self.WEST, self.EAST]
        for tab in tabs:
            assert isinstance(tab, tuple)
        self.content = [(tab_label, structure_to_form(tab_form)) for tab_label, tab_form in tabs]
        # TODO: to be validated that this removal is justified.
        #self.content = sum((tab_form.get_fields() for tab_label, tab_form in self.tabs), [])

    @property
    def tabs(self):
        return self.content
    
    def __str__(self):
        return 'TabForm { %s\n        }' % (u'\n  '.join('%s : %s' % (label, str(form)) for label, form in self.tabs))

    def add_tab_at_index(self, tab_label, tab_form, index):
        """Add a tab to the form at the specified index

        :param tab_label: the name to the tab
        :param tab_form: the form to display in the tab or a list of field names.
        :param index: the position of tab in the tabs list.
        """
        tab_form = structure_to_form(tab_form)
        self.tabs.insert(index, (tab_label, tab_form))

    def add_tab(self, tab_label, tab_form):
        """Add a tab to the form

        :param tab_label: the name of the tab
        :param tab_form: the form to display in the tab or a list of field names.
        """
        tab_form = structure_to_form(tab_form)
        self.tabs.append((tab_label, tab_form))

    def get_tab(self, tab_label):
        """Get the tab form of associated with a tab_label, use this function to
        modify the underlying tab_form in case of inheritance

        :param tab_label : a label of a tab as passed in the construction method
        :return: the tab_form corresponding to tab_label
        """
        for label, form in self.tabs:
            if label == tab_label:
                return form

    def replace_field(self, original_field, new_field):
        super(TabForm, self).replace_field(original_field, new_field)
        for _label, form in self.tabs:
            if form.replace_field(original_field, new_field):
                return True
        return False

    def remove_field(self, original_field):
        super(TabForm, self).remove_field(original_field)
        for _label, form in self.tabs:
            if form.remove_field(original_field):
                return True
        return False

    def _get_fields_from_form(self):
        for _label, form in self.tabs:
            for field in form._get_fields_from_form():
                yield field

    @classmethod
    def render(cls, widgets, form, parent=None, toplevel=False):
        if isinstance(form, bytes):
            form = json.loads(form)
        if isinstance(form, list):
            form = form[1]
        logger.debug('rendering %s' % cls.__name__)
        widget = DelayedTabWidget(widgets, form["content"], parent)
        widget.setTabPosition(getattr(QtWidgets.QTabWidget, form["position"]))
        return widget

@dataclass
class HBoxForm(AbstractForm):
    """
  Render different forms in a horizontal box::

    form = forms.HBoxForm([['title', 'short_description'], ['director', 'release_date']])

  .. image:: /_static/form/hbox_form.png

  :param columns: a list of forms to display in the different columns of the horizontal box
  """

    title: str = field(init=False, default=None)
    content: list
    scrollbars: bool = False

    def __post_init__(self):
        assert isinstance(self.content, list)
        self.content = [structure_to_form(col) for col in self.content]
    
    def __str__(self):
        return 'HBoxForm [ %s\n         ]' % ('         \n'.join([str(form) for form in self.content]))

    def replace_field(self, original_field, new_field):
        for form in self.content:
            if form.replace_field(original_field, new_field):
                return True
        return False

    def _get_fields_from_form(self):
        for form in self.content:
            for field in form._get_fields_from_form():
                yield field

    @classmethod
    def render(cls, widgets, form, parent=None, toplevel=False):
        if isinstance(form, bytes):
            form = json.loads(form)
        if isinstance(form, list):
            form = form[1]
        logger.debug('rendering %s' % cls.__name__)
        widget = QtWidgets.QWidget(parent)
        form_layout = QtWidgets.QHBoxLayout()
        for form in form["content"]:
            form_class = MetaForm.forms.get(form[0])
            f = form_class.render(widgets, form[1], parent=widget, toplevel=False)
            if isinstance(f, QtWidgets.QLayout):
                form_layout.addLayout(f)
            elif isinstance(f, QtWidgets.QLayoutItem):
                form_layout.addItem(f)
            else:
                form_layout.addWidget(f)
        widget.setLayout(form_layout)
        return widget

@dataclass
class VBoxForm(AbstractForm):
    """
  Render different forms or widgets in a vertical box::

    form = forms.VBoxForm([['title', 'short_description'], ['director', 'release_date']])
    
  .. image:: /_static/form/vbox_form.png
  
  :param rows: a list of forms to display in the different rows of the vertical box
  """

    title: str = field(init=False, default=None)
    rows: InitVar[list]

    def __post_init__(self, rows):
        assert isinstance(rows, list)
        self.content = [structure_to_form(row) for row in rows]
        # TODO: to be validated that this removal is justified.
        #self.content = sum((row_form.get_fields() for row_form in self.rows), [])

    @property
    def rows(self):
        return self.content
    
    def replace_field(self, original_field, new_field):
        for form in self.rows:
            if form.replace_field(original_field, new_field):
                return True
        return False

    def _get_fields_from_form(self):
        for form in self.rows:
            for field in form._get_fields_from_form():
                yield field

    def __str__(self):
        return 'VBoxForm [ %s\n         ]' % ('         \n'.join([str(form) for form in self.rows]))

    @classmethod
    def render(cls, widgets, form, parent=None, toplevel=False):
        if isinstance(form, bytes):
            form = json.loads(form)
        if isinstance(form, list):
            form = form[1]        
        logger.debug('rendering %s' % cls.__name__)
        widget = QtWidgets.QWidget(parent)
        form_layout = QtWidgets.QVBoxLayout()
        for form in form["content"]:
            form_class = MetaForm.forms.get(form[0])
            f = form_class.render(widgets, form[1], widget, False)
            if isinstance(f, QtWidgets.QLayout):
                form_layout.addLayout(f)
            elif isinstance(f, QtWidgets.QLayoutItem):
                form_layout.addItem(f)
            else:
                form_layout.addWidget(f)
        widget.setLayout(form_layout)
        return widget

@dataclass
class ColumnSpan(AbstractForm):

    title: str = field(init=False, default=None)
    field: InitVar[str] = None
    num: InitVar[int] = 2
    
    def __post_init__(self, field, num):
        self.content = [field]
        self.columns = num
    
    @property
    def field(self):
        for field in self.content:
            return field
    
    @property
    def num(self):
        return self.columns

@dataclass
class GridForm(AbstractForm):
    """Put different fields into a grid, without a label.  Row or column labels can be added
  using the :class:`Label` form::

    GridForm([['title', 'short_description'], ['director','release_date']])
    :param grid: A list for each row in the grid, containing a list with all fields that should be put in that row
  .. image:: /_static/form/grid_form.png
  """

    title: str = field(init=False, default=None)
    grid: InitVar[list]
    nomargins: bool = False

    def __post_init__(self, grid):
        assert isinstance( grid, list )
        fields = []
        for row in grid:
            assert isinstance( row, list )
            fields.extend(row)
        self.content = grid
    
    @property
    def grid(self):
        return self.content
    
    def _get_fields_from_form(self):
        for row in self.grid:
            for field in row:
                if field is None:
                    continue
                elif issubclass(type(field), AbstractForm):
                    for nested_field in field._get_fields_from_form():
                        yield nested_field
                else:
                    assert isinstance(field, str) or (field is None)
                    yield field
    
    def append_row(self, row):
        """:param row: the list of fields that should come in the additional row
        use this method to modify inherited grid forms"""
        assert isinstance(row, list)
        self.grid.append(row)

    def append_column(self, column):
        """:param column: the list of fields that should come in the additional column
        use this method to modify inherited grid forms"""
        assert isinstance(column, list)
        for row, additional_field in zip(self.grid, column):
            row.append(additional_field)

    @classmethod
    def render(cls, widgets, form, parent=None, toplevel=False):
        if isinstance(form, bytes):
            form = json.loads(form)
        if isinstance(form, list):
            form = form[1]

        widget = QtWidgets.QWidget(parent)
        grid_layout = QtWidgets.QGridLayout()
        for i, row in enumerate(form["content"]):
            skip = 0
            for j, field in enumerate(row):
                num = 1
                col = j + skip
                if isinstance(field, list):
                    field_class = MetaForm.forms.get(field[0])
                    field_content = field[1]
                    if isinstance(field_class, ColumnSpan):
                        num = field_content["columns"]
                        field = field_content["content"][0]
                    if issubclass(field_class, AbstractForm):
                        form = field_class.render(widgets, field_content, parent)
                        if isinstance(form, QtWidgets.QWidget):
                            grid_layout.addWidget(form, i, col, 1, num)
                        elif isinstance(form, QtWidgets.QLayoutItem):
                            grid_layout.addItem(form, i, col, 1, num)
                        elif isinstance(form, QtWidgets.QLayout):
                            grid_layout.addLayout(form, i, col, 1, num)
                        skip += num - 1
                else:
                    editor = widgets.create_editor(field, widget)
                    grid_layout.addWidget(editor, i, col, 1, num)
                    skip += num - 1

        widget.setLayout(grid_layout)
        if not toplevel:
            grid_layout.setContentsMargins(0, 0, 0, 0)

        return widget

@dataclass
class WidgetOnlyForm(AbstractForm):
    """Renders a single widget without its label, typically a one2many widget"""

    title: str = field(init=False, default=None)
    field: InitVar[str]

    def __post_init__(self, field):
        assert isinstance( field, str )
        self.content = [field]

    @property
    def field(self):
        for field in self.content:
            return field
        
    @classmethod
    def render(cls, widgets, form, parent=None, toplevel=False):
        if isinstance(form, bytes):
            form = json.loads(form)
        if isinstance(form, list):
            form = form[1]

        logger.debug('rendering %s' % cls.__name__)
        editor = widgets.create_editor(form["content"][0], parent)
        return editor

@dataclass
class Stretch(AbstractForm):
    """A stretchable space with zero minimum size, this is able to fill a gap
    in the form if there are no other items to fill this space.
    """

    title: str = field(init=False, default=None)
    content: list = field(init=False, default_factory=list)
    
    @classmethod
    def render(cls, widgets, form, parent=None, toplevel=False):
        return QtWidgets.QSpacerItem(0, 0, vPolicy=QtWidgets.QSizePolicy.Expanding)

@dataclass
class GroupBoxForm(AbstractForm):
    """
  Renders a form within a QGroupBox::

    class Admin(EntityAdmin):
      form_display = GroupBoxForm('Movie', ['title', 'short_description'])

  .. image:: /_static/form/group_box_form.png
  """
    
    title: str
    content: Any
    scrollbars: bool = None
    min_width: int = None
    min_height: int = None
    columns: int = 1

    def __post_init__(self):
        if issubclass(type(self.content), AbstractForm):
            self.content = [self.content]

    @classmethod
    def render(cls, widgets, form, parent=None, toplevel=False):
        if isinstance(form, bytes):
            form = json.loads(form)
        if isinstance(form, list):
            form = form[1]

        widget = QtWidgets.QGroupBox(str(form["title"]), parent)
        layout = QtWidgets.QVBoxLayout()
        if form["min_width"] and form["min_height"]:
            widget.setMinimumSize(form["min_width"], form["min_height"])
        widget.setLayout(layout)
        form = super(GroupBoxForm, cls).render(widgets, form, widget, toplevel=False)
        layout.addWidget(form)
        return widget

def structure_to_form(structure):
    """Convert a python data structure to a form, using the following rules :

   * if structure is an instance of Form, return structure
   * if structure is a list, create a Form from this list

  This function is mainly used in the Admin class to construct forms out of
  the form_display attribute
    """
    if issubclass(type(structure), AbstractForm):
        return structure
    return Form(structure)
