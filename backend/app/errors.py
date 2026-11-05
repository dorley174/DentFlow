def validation_message(error):
    kind=error.get('type','')
    messages={
      'missing':'Обязательное поле',
      'extra_forbidden':'Лишнее поле не допускается',
      'literal_error':'Выберите допустимое значение',
      'string_too_short':'Значение слишком короткое',
      'string_too_long':'Значение слишком длинное',
      'string_pattern_mismatch':'Некорректный формат',
      'int_parsing':'Введите целое число',
      'bool_parsing':'Ожидается да или нет',
      'greater_than_equal':'Значение меньше допустимого минимума',
      'less_than_equal':'Значение больше допустимого максимума',
      'multiple_of':'Значение должно соответствовать допустимому шагу',
      'datetime_from_date_parsing':'Укажите корректную дату и время',
      'date_from_datetime_parsing':'Укажите корректную дату',
      'json_invalid':'Некорректный JSON-запрос',
    }
    if kind=='value_error':
        return str(error.get('ctx',{}).get('error','Некорректное значение'))
    return messages.get(kind,'Некорректное значение')
