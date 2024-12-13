
from erpnext.stock.doctype.item.item import Item
from frappe.utils import cstr
import frappe
from frappe import _
import copy


class OverrideItem(Item):
    def update_variants(self):
        print("update_variants")
        if self.flags.dont_update_variants or frappe.db.get_single_value(
            "Item Variant Settings", "do_not_update_variants"
        ):
            return
        if self.has_variants:
            variants = frappe.db.get_all("Item", fields=["item_code"], filters={"variant_of": self.name})
            if variants:
                if len(variants) <= 30:
                    update_variants(variants, self, publish_progress=False)
                    frappe.msgprint(_("Item Variants updated"))
                else:
                    frappe.enqueue(
                        "erpnext.stock.doctype.item.item.update_variants",
                        variants=variants,
                        template=self,
                        now=frappe.flags.in_test,
                        timeout=600,
                        enqueue_after_commit=True,
                    )

def update_variants(variants, template, publish_progress=True):
    total = len(variants)
    for count, d in enumerate(variants, start=1):
        variant = frappe.get_doc("Item", d)
        copy_attributes_to_variant(template, variant)
        variant.save()
        if publish_progress:
            frappe.publish_progress(count / total * 100, title=_("Updating Variants..."))


def copy_attributes_to_variant(item, variant):
    # copy non no-copy fields

    exclude_fields = [
        "naming_series",
        "item_code",
        "item_name",
        "published_in_website",
        "opening_stock",
        "variant_of",
        "valuation_rate",
        "disabled"
    ]

    if item.variant_based_on == "Manufacturer":
        # don't copy manufacturer values if based on part no
        exclude_fields += ["manufacturer", "manufacturer_part_no"]

    allow_fields = [d.field_name for d in frappe.get_all("Variant Field", fields=["field_name"])]
    if "variant_based_on" not in allow_fields:
        allow_fields.append("variant_based_on")
    for field in item.meta.fields:
        # "Table" is part of `no_value_field` but we shouldn't ignore tables
        if (field.reqd or field.fieldname in allow_fields) and field.fieldname not in exclude_fields:
            if variant.get(field.fieldname) != item.get(field.fieldname):
                if field.fieldtype == "Table":
                    variant.set(field.fieldname, [])
                    for d in item.get(field.fieldname):
                        row = copy.deepcopy(d)
                        if row.get("name"):
                            row.name = None
                        variant.append(field.fieldname, row)
                else:
                    variant.set(field.fieldname, item.get(field.fieldname))

    variant.variant_of = item.name

    if "description" not in allow_fields:
        if not variant.description:
            variant.description = ""
    else:
        if item.variant_based_on == "Item Attribute":
            if variant.attributes:
                attributes_description = item.description + " "
                for d in variant.attributes:
                    attributes_description += (
                        "<div>" + d.attribute + ": " + cstr(d.attribute_value) + "</div>"
                    )

                if attributes_description not in variant.description:
                    variant.description = attributes_description

