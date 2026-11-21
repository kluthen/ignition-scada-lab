"""OPC UA server whose address space is generated from the registry (asyncua).

- Namespaces are registered in the order cell, robot, sim (indexes 2, 3, 4).
- Each node's string NodeId is its signal name, with the cell id of this
  instance for the cell's own nodes (instance.py: C03.Status.StateCurrent);
  BrowseName/DisplayName is the last path segment; Description is the CSV description.
- RW variables are writable by clients. Each scan:
    pull()  copies client writes from the address space into the Tags,
    push()  publishes values the program changed.
"""

from __future__ import annotations

import datetime as dt
import logging

from asyncua import Server, ua

from registry import Signal
from tags import Tags

log = logging.getLogger("opcua")

NAMESPACES = ["urn:ignition-lab:cell", "urn:ignition-lab:robot", "urn:ignition-lab:sim"]
VTYPES = {
    "Boolean": ua.VariantType.Boolean, "Byte": ua.VariantType.Byte, "UInt16": ua.VariantType.UInt16,
    "Int32": ua.VariantType.Int32, "UInt32": ua.VariantType.UInt32, "Double": ua.VariantType.Double,
    "String": ua.VariantType.String, "DateTime": ua.VariantType.DateTime,
}


class OpcUaServer:
    def __init__(self, tags: Tags, endpoint: str, cell: str):
        self.tags = tags
        self.endpoint = endpoint
        self.cell = cell
        self.server = Server()
        self.ns: dict[str, int] = {}
        self.nodeids: dict[str, ua.NodeId] = {}
        self.vtypes: dict[str, ua.VariantType] = {}
        self.published: dict[str, object] = {}
        self.writable: list[str] = []

    async def start(self) -> None:
        srv = self.server
        await srv.init()
        srv.set_endpoint(self.endpoint)
        srv.set_server_name(f"Ignition lab: Cell {self.cell[1:]} controller (simulation)")
        await srv.set_application_uri(f"urn:ignition-lab:plc-sim:{self.cell.lower()}")
        srv.set_security_policy([ua.SecurityPolicyType.NoSecurity])
        for uri in NAMESPACES:
            self.ns[uri] = await srv.register_namespace(uri)
        await self._build()
        await srv.start()
        log.info("OPC UA server on %s, namespaces %s, %d variables (%d writable)",
                 self.endpoint, self.ns, len(self.nodeids), len(self.writable))

    async def _build(self) -> None:
        objects = self.server.nodes.objects
        nodes_by_path = {"/Objects": objects}
        rows = [s for s in self.tags.signals.values() if s.protocol == "opcua"]
        # parents before children: sort by path depth, keep CSV order otherwise
        rows.sort(key=lambda s: s.browse_path.count("/"))
        for s in rows:
            parent_path, _, leaf = s.browse_path.rpartition("/")
            parent = nodes_by_path[parent_path]
            idx = self.ns[s.namespace_uri]
            nodeid = ua.NodeId(s.node_id, idx)
            bname = ua.QualifiedName(leaf, idx)
            if s.node_class == "Object":
                if s.type_definition == "FolderType":
                    node = await parent.add_folder(nodeid, bname)
                else:
                    node = await parent.add_object(nodeid, bname)
            else:
                vtype = VTYPES[s.data_type]
                value = self.tags[s.name]
                if s.type_definition == "PropertyType":
                    node = await parent.add_property(nodeid, bname, value, vtype)
                else:
                    node = await parent.add_variable(nodeid, bname, value, vtype)
                if s.access == "RW":
                    await node.set_writable()
                    self.writable.append(s.name)
                self.nodeids[s.name] = nodeid
                self.vtypes[s.name] = vtype
                self.published[s.name] = value
            if s.description:
                await node.write_attribute(ua.AttributeIds.Description, ua.DataValue(
                    ua.Variant(ua.LocalizedText(s.description, "en"), ua.VariantType.LocalizedText)))
            nodes_by_path[s.browse_path] = node

    def pull(self) -> list[str]:
        """Copy client writes into the tags. Returns the names that changed."""
        changed = []
        for name in self.writable:
            value = self.server.read_attribute_value(self.nodeids[name]).Value.Value
            if value != self.published[name]:
                self.published[name] = value
                self.tags[name] = value
                changed.append(name)
        return changed

    async def push(self) -> None:
        now = dt.datetime.now(dt.timezone.utc)
        for name, nodeid in self.nodeids.items():
            value = self.tags[name]
            if value != self.published[name]:
                await self.server.write_attribute_value(nodeid, ua.DataValue(
                    ua.Variant(value, self.vtypes[name]), SourceTimestamp=now, ServerTimestamp=now))
                self.published[name] = value

    async def stop(self) -> None:
        await self.server.stop()
