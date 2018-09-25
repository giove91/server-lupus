from django import forms

class MultiSelect(forms.SelectMultiple):
    class Media:
        css = {
            'screen': ('multiselect/css/multi-select.css',)
        }
        js = ('multiselect/js/jquery.multi-select.js', )


