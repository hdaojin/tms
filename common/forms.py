# common/forms.py
"""
自定义表单基类，提供自定义的表单渲染
"""

from django import forms


class StyledFormMixin:
    """
    表单样式混入，自动为表单字段添加CSS类
    用法:
        class MyForm(StyledFormMixin, forms.Form):
        class MyModelForm(StyledFormMixin, forms.ModelForm):
            ...
    """
    default_mapping = {
        # 输入框
        (forms.TextInput, forms.NumberInput, forms.EmailInput, forms.URLInput, forms.PasswordInput, forms.DateInput, forms.DateTimeInput, forms.TimeInput): 'input w-full',
        # 文件上传框
        (forms.FileInput,): 'file-input w-full file-input-primary',
        (forms.ClearableFileInput,): 'file-input w-full file-input-primary',
        # 选择框
        (forms.Select, forms.SelectMultiple): 'select w-full',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for  field in self.fields.values():  # type: ignore
            widget_type = type(field.widget)
            for types, css_class in self.default_mapping.items():
                if widget_type in types:
                    existing_classes = field.widget.attrs.get('class', '')
                    if existing_classes:
                        field.widget.attrs['class'] = f"{existing_classes} {css_class}"
                    else:
                        field.widget.attrs['class'] = css_class
                    break
