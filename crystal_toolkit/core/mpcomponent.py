import logging
from abc import ABC, abstractmethod
from datetime import datetime
from json import dumps, loads
from time import mktime
from warnings import warn

import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Output, Input, State
from monty.json import MontyEncoder, MontyDecoder
from pymatgen import MPRester

from flask_caching import Cache

# fallback cache if Redis etc. isn't set up
null_cache = Cache(config={"CACHE_TYPE": "null"})


class MPComponent(ABC):

    _app_stores = []
    app = None
    cache = null_cache

    @staticmethod
    def register_app(app):
        MPComponent.app = app

    @staticmethod
    def register_cache(cache):
        MPComponent.cache = cache

    @staticmethod
    def all_app_stores():
        return html.Div(MPComponent._app_stores)

    def __init__(
        self,
        contents=None,
        id=None,
        origin_component=None,
        storage_type="memory",
        static=False,
    ):
        """
        :param id: a unique id for this component, if not specified a random
        one will be chosen
        :param origin_component: if specified, component will reference the
        Store in the origin MPComponent instead of creating its own Store
        :param contents: an object that can be serialized using the MSON
        protocol, can be set to None initially
        """

        if id is None:
            id = self.__class__.__name__

        self._id = id
        self._all_ids = set()
        self._stores = {}

        if MPComponent.app is None:
            warn(
                f"No app defined for component {self._id}, "
                f"callbacks cannot be created. Please register app using "
                f"MPComponent.register_app(app)."
            )

        if MPComponent.cache is null_cache:
            warn(
                f"No cache is defined for component {self._id}, "
                f"performance of app may be degraded. Please register cache "
                f"using MPComponent.register_cache(cache)."
            )

        if origin_component is None:
            self._canonical_store_id = self._id
            self.create_store(
                name="default", initial_data=contents, storage_type=storage_type
            )
            self.initial_data = self.to_data(contents)
        else:
            if MPComponent.app is None:
                raise ValueError("Can only link stores if an app is defined.")
            self._canonical_store_id = origin_component._canonical_store_id
            self.initial_data = origin_component.initial_data

        if MPComponent.app and not static:
            self.generate_callbacks(MPComponent.app, MPComponent.cache)

        self.logger = logging.getLogger(self.__class__.__name__)

    def id(self, name="default"):
        if name != "default":
            name = f"{self._id}_{name}"
        else:
            name = self._canonical_store_id
        self._all_ids.add(name)
        return name

    def create_store(
        self, name, initial_data=None, storage_type="memory", debug_clear=False
    ):
        store = dcc.Store(
            id=self.id(name),
            data=self.to_data(initial_data),
            storage_type=storage_type,
            clear_data=debug_clear,
        )
        self._stores[name] = store
        MPComponent._app_stores.append(store)

    @staticmethod
    def to_data(msonable_obj):
        """
        Converts any MSONable object into a format suitable for storing in
        a dcc.Store

        :param msonable_obj: Any MSONable object
        :return: A JSON string (a string is preferred over a dict since this can
        be easily memoized)
        """
        if msonable_obj is None:
            return None
        data_str = dumps(msonable_obj, cls=MontyEncoder, indent=4)
        if MPComponent.cache != null_cache:
            pass
            # token = str(uuid4())[0:6]
            ## set to 1 week expiration by default
            # cache.set(token, data_str, timeout=604_800,
            #          key_prefix="crystal_toolkit_callback_")
            # return {'token': token}
        return data_str

    @staticmethod
    def from_data(data):
        """
        Converts the contents of a dcc.Store back into a Python object.
        :param data: contents of a dcc.Store created by to_data
        :return: a Python object
        """
        return loads(data, cls=MontyDecoder)

    def attach_from(
        self, origin_component, origin_store_name="default", this_store_name="default"
    ):
        """
        Link two MPComponents together.

        :param origin_component: An MPComponent
        :param origin_store_name: The suffix for the Store layout in the
        origin component, e.g. "structure" or "mpid", if None will link to
        the component's default Store
        :param this_store_name: The suffix for the Store layout in this
        component to be linked to, this is usually equal to the
        origin_store_suffix
        :return:
        """

        if MPComponent.app is None:
            raise AttributeError("No app defined, callbacks cannot be created.")

        origin_store_id = origin_component.id(origin_store_name)
        dest_store_id = self.id(this_store_name)

        self.logger.debug(
            f"Linking the output of {origin_store_id} to {dest_store_id}."
        )

        @MPComponent.app.callback(
            Output(dest_store_id, "data"),
            [Input(origin_store_id, "modified_timestamp")],
            [State(origin_store_id, "data")],
        )
        def update_store(modified_timestamp, data):
            return data

    def __getattr__(self, item):
        # TODO: remove, this isn't helpful (or add autocomplete)
        if item == "supported_stores":
            raise AttributeError  # prevent infinite recursion
        if item.endswith("store") and item.split("_store")[0] in self.supported_stores:
            return self.id(item)
        elif (
            item.endswith("layout")
            and item.split("_layout")[0] in self.supported_layouts
        ):
            return self.all_layouts[item.split("_layout")[0]]
        else:
            raise AttributeError

    @property
    def supported_stores(self):
        return self._stores.keys()

    @property
    def supported_layouts(self):
        return self.all_layouts.keys()

    @property
    def supported_ids(self):
        return list(self._all_ids)

    def __repr__(self):
        return f"""{self.id()}<{self.__class__.__name__}>
IDs: {list(self.supported_ids)}
Stores: {list(self.supported_stores)}
Layouts: {list(self.supported_layouts)}"""

    @property
    @abstractmethod
    def all_layouts(self):
        """
        Layouts associated with this component.

        All individual layout ids *must* be derived from main id followed by an
        underscore, for example, for an input box layout a suitable id name
        might be f"{self.id}_input".

        The underlying store (self._store) *must* be included in self.layouts.

        :return: A dictionary with names of layouts as keys (str) and Dash
        layouts as values. Preferred keys include:
        "main" for the primary layout for this component,
        "label" for a html.Label describing the component with className
        "mpc_label",
        "help" for a dcc.Markdown component explaining how it works,
        "controls" for controls to interact with the component (for example to
        change how the data is displayed) with className "mpc_help",
        "error" for a component that will display any appropriate errors, this
        should contain a html.Div with className "mpc_error", and
        "warning" for a component that will display any appropriate warnings,
        this should contain a html.Div with className "mpc_warning".

        These layouts are not mandatory but are at the discretion of the
        component author.
        """
        return {}

    @property
    def standard_layout(self):
        """
        :return: A Dash layout for the full component, for example including
        both the main component and controls for that component. Must
        """
        return html.Div(list(self.all_layouts.values()))

    @abstractmethod
    def generate_callbacks(self, app, cache):
        """
        Generate all callbacks associated with the layouts in this app. Assume
        that "suppress_callback_exceptions" is True, since it is not always
        guaranteed that all layouts will be displayed to the end user at all
        times, but it's important the callbacks are defined on the server.
        """
        raise NotImplementedError

    @staticmethod
    def get_time() -> float:
        """
        :return: Current time as a float. Use with caution!
        """
        return mktime(datetime.now().timetuple())
