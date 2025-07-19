# single_type_page.py
#
# Copyright 2023 Nokse
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from gi.repository import Gtk
from gi.repository import GLib

import threading

from .page import Page
from ..widgets import HTCardWidget

from ..lib import utils

from ..disconnectable_iface import IDisconnectable

from tidalapi.types import ItemOrder, OrderDirection


class fromFunctionPage(Page):
    __gtype_name__ = "fromFunctionPage"

    """Used to display lists of albums/artists/mixes/playlists and tracks
    from a request function"""

    def __init__(self, _type, _title=""):
        IDisconnectable.__init__(self)
        super().__init__()

        self.function = None
        self.type = _type

        self.set_title(_title)

        self.parent = None

        self.items = []

        self.items_limit = 50
        self.items_n = 0

        self.sort_button = None

        self.sort_items_by = ItemOrder.Date
        self.order_direction = OrderDirection.Descending
        self.order_direction_changed = False

        self.handler_id = self.scrolled_window.connect(
            "edge-overshot", self.on_edge_overshot
        )
        self.signals.append((self.scrolled_window, self.handler_id))

    def set_function(self, function):
        self.function = function

    def set_items(self, items):
        self.items = items

    def on_edge_overshot(self, scrolled_window, pos):
        if pos == Gtk.PositionType.BOTTOM:
            threading.Thread(target=self.th_load_items).start()

    def _th_load_page(self):
        self.th_load_items()

        self._page_loaded()

    def add_page_scaffolding(self):
        # Create a horizontal box to act as a filter/sort bar
        filter_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        filter_bar.add_css_class("toolbar")
        filter_bar.set_margin_top(12)
        filter_bar.set_margin_bottom(12)
        filter_bar.set_margin_start(12)
        filter_bar.set_margin_end(12)

        # Helper to create sort buttons
        def create_sort_button(label, sort_key):
            btn = Gtk.Button(label=label)
            btn.connect("clicked", lambda _, key=sort_key: self.on_sort_clicked(key))
            return btn

        # Add sort buttons for Name, Artist, Album, Date Added
        name_btn = create_sort_button("Name", "name")
        artist_btn = create_sort_button("Artist", "artist")
        album_btn = create_sort_button("Album", "album")
        date_btn = create_sort_button("Date Added", "date_added")

        filter_bar.append(name_btn)
        filter_bar.append(artist_btn)
        filter_bar.append(album_btn)
        filter_bar.append(date_btn)

        GLib.idle_add(self.page_content.append, filter_bar)
        self.sort_button = filter_bar

        self.parent = Gtk.ListBox(
            css_classes=["tracks-list-box"],
            margin_bottom=12,
            margin_start=12,
            margin_end=12,
            margin_top=12,
        )
        GLib.idle_add(self.page_content.append, self.parent)
        self.signals.append((
            self.parent,
            self.parent.connect("row-activated", self.on_tracks_row_selected),
        ))

    def th_load_items(self):
        new_items = []
        if self.function:
            new_items = self.function(
                limit=self.items_limit,
                offset=(self.items_n),
                sort_by=self.sort_items_by,
                order_direction=self.order_direction
            )
            # If we're reloading with new tracks (e.g., sort changed), clear old content
            if self.items_n == 0 or self.order_direction_changed and self.parent is not None:
                self.add_page_scaffolding()
            else:
                self.items.extend(new_items)

            if not new_items:
                self.scrolled_window.disconnect(self.handler_id)
                return
        else:
            new_items = self.items
            self.scrolled_window.disconnect(self.handler_id)

        if self.type == "track":
            self.add_tracks(new_items)
        else:
            self.add_cards(new_items)

        self.items_n += self.items_limit
        # Reset flag after reload
        self.order_direction_changed = False

    def add_tracks(self, new_items):
        if self.parent is None:
            print("Scaffolding page initially")
            self.add_page_scaffolding()

        for index, track in enumerate(new_items):
            listing = self.get_track_listing(track)
            listing.set_name(str(index + self.items_n))
            GLib.idle_add(self.parent.append, listing)

    def on_sort_clicked(self, filter_key):
        print("Sort button clicked")

        if filter_key == "name":
            self.sort_items_by = ItemOrder.Name
        elif filter_key == "artist":
            self.sort_items_by = ItemOrder.Artist
        elif filter_key == "album":
            self.sort_items_by = ItemOrder.Album
        elif filter_key == "date_added":
            self.sort_items_by = ItemOrder.Date

        self.order_direction = OrderDirection.Ascending if self.order_direction == OrderDirection.Descending else OrderDirection.Descending
        print(f"New order direction: {self.order_direction}")

        self.order_direction_changed = True
        self.items_n = 0

        # FIXME Remove old list, this is probably not the right way to do it in GTK!
        if self.parent:
            self.page_content.remove(self.parent)
            self.page_content.remove(self.sort_button)
            self.parent = None

        self.th_load_items()
        self._page_loaded()

    def add_cards(self, new_items):
        if self.parent is None:
            self.parent = Gtk.FlowBox(selection_mode=0)
            self.page_content.append(self.parent)

        for index, item in enumerate(new_items):
            card = HTCardWidget(item)
            GLib.idle_add(self.parent.append, card)

    def on_tracks_row_selected(self, list_box, row):
        index = int(row.get_name())

        utils.player_object.play_this(self.items, index)
