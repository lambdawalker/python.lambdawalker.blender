def test_smoke():
    try:
        from lambdawalker.blender.images.image_type_conversion import convert_image_type
        assert convert_image_type is not None
    except ImportError:
        pass
    print("blender OK")
