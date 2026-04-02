# core/forms.py
"""
自定义表单基类，提供自定义的表单渲染
"""
from __future__ import annotations

from typing import Any, Dict, Tuple, Type

from django import forms


class StyledFormMixin:
    """
    表单样式混入，自动为表单字段添加 DaisyUI CSS 类
    
    特性:
    - 自动为常见表单控件添加统一的 DaisyUI 样式
    - 保留已有的 CSS 类（追加而非覆盖）
    - 可通过 style_mapping 自定义样式映射
    
    用法:
        class MyForm(StyledFormMixin, forms.Form):
            ...
        
        class MyModelForm(StyledFormMixin, forms.ModelForm):
            ...
        
        # 自定义样式映射
        class MyForm(StyledFormMixin, forms.Form):
            style_mapping = {
                (forms.TextInput,): 'input input-bordered w-full',
            }
    """
    
    # 默认样式映射，子类可覆盖
    default_mapping: Dict[Tuple[Type[forms.Widget], ...], str] = {
        # 输入框
        (forms.TextInput, forms.NumberInput, forms.EmailInput, 
         forms.URLInput, forms.PasswordInput, forms.DateInput, 
         forms.DateTimeInput, forms.TimeInput): 'input w-full',
        # 多行文本框
        (forms.Textarea,): 'textarea w-full',
        # 文件上传框
        (forms.FileInput,): 'file-input w-full file-input-primary',
        (forms.ClearableFileInput,): 'file-input w-full file-input-primary',
        # 下拉选择框
        (forms.Select, forms.SelectMultiple): 'select w-full',
        # 单个复选框
        (forms.CheckboxInput,): 'checkbox checkbox-primary',
        # 多个复选框
        (forms.RadioSelect,): 'radio radio-primary',
    }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # 获取自定义映射或使用默认映射
        mapping = getattr(self, 'style_mapping', self.default_mapping)
        
        for field in self.fields.values():  # type: ignore
            widget_type = type(field.widget)
            for types, css_class in mapping.items():
                if widget_type in types:
                    # 保留已有的 CSS 类，追加新类
                    existing_classes = field.widget.attrs.get('class', '')
                    if existing_classes:
                        # 避免重复添加相同的类
                        existing_set = set(existing_classes.split())
                        new_set = set(css_class.split())
                        combined = existing_set | new_set
                        field.widget.attrs['class'] = ' '.join(sorted(combined))
                    else:
                        field.widget.attrs['class'] = css_class
                    break

