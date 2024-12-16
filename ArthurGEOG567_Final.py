import arcpy
import os

# Define the input parameters
input_csv = arcpy.GetParameterAsText(0)  # Path to the input CSV file
output_gdb = arcpy.GetParameterAsText(1) # Path to the default geodatabase
output_fc = arcpy.GetParameterAsText(2)  # Output feature class name
dem_path = arcpy.GetParameterAsText(3)   # Path to the local DEM TIFF file
clipped_dem = arcpy.GetParameterAsText(4)  # Output path for the clipped DEM

# Define the spatial reference for WGS 1984
wgs84 = arcpy.SpatialReference(4326)

# Define the spatial reference for Alberta 3TM 114
alberta_3tm = arcpy.SpatialReference(3776)

try:
    # Create a temporary table from the CSV
    temp_table = "in_memory\\temp_table"
    arcpy.TableToTable_conversion(input_csv, "in_memory", "temp_table")

    # Define the X and Y fields (assuming 'Longitude' and 'Latitude' are the field names in your CSV)
    x_field = "Longitude"
    y_field = "Latitude"

    # Check if the required fields exist in the CSV
    field_names = [field.name for field in arcpy.ListFields(temp_table)]
    for field in [x_field, y_field]:
        if field not in field_names:
            arcpy.AddError(f"CSV must contain fields '{x_field}' and '{y_field}'")
            raise ValueError(f"CSV must contain fields '{x_field}' and '{y_field}'")

    # Create the point feature class in WGS 1984
    temp_fc_wgs84 = "in_memory\\temp_fc_wgs84"
    arcpy.management.XYTableToPoint(temp_table, temp_fc_wgs84, x_field, y_field, "", wgs84)

    # Verify if the DEM file exists and is a valid raster
    if not arcpy.Exists(dem_path):
        arcpy.AddError(f"DEM file at '{dem_path}' does not exist.")
        raise ValueError(f"DEM file at '{dem_path}' does not exist.")
    if arcpy.Describe(dem_path).dataType != 'RasterDataset':
        arcpy.AddError(f"The file at '{dem_path}' is not a valid raster dataset.")
        raise ValueError(f"The file at '{dem_path}' is not a valid raster dataset.")

    # Project the point feature class from WGS 1984 to Alberta 3TM 114 NAD 83
    output_fc_path = os.path.join(output_gdb, output_fc)
    arcpy.management.Project(temp_fc_wgs84, output_fc_path, alberta_3tm)
    arcpy.AddMessage("Projected point feature class to Alberta 3TM 114 NAD 83")

    # Project the DEM to the same spatial reference as the points (Alberta 3TM 114)
    projected_dem = "in_memory\\projected_dem"
    arcpy.management.ProjectRaster(dem_path, projected_dem, alberta_3tm)
    arcpy.AddMessage("Projected DEM to Alberta 3TM 114")

    # Clip the DEM to the extent of the points
    # Determine the extent of the points
    extent = arcpy.Describe(output_fc_path).extent
    xmin, ymin, xmax, ymax = extent.XMin, extent.YMin, extent.XMax, extent.YMax

    # Buffer the extent slightly to ensure overlap
    buffer = 5000  # Adjust buffer size as needed
    xmin -= buffer
    ymin -= buffer
    xmax += buffer
    ymax += buffer

    # Clip the DEM using the buffered extent
    arcpy.AddMessage("Clipping DEM to the extent of points...")
    arcpy.management.Clip(
        projected_dem,
        f"{xmin} {ymin} {xmax} {ymax}",
        clipped_dem,
        "#",
        "#",
        "NONE",
        "MAINTAIN_EXTENT"
    )
    arcpy.AddMessage(f"Clipped DEM saved to {clipped_dem}")

    # Generate topographic layers using the clipped DEM
    # Define output raster paths for slope, aspect, curvature, and hillshade
    slope_raster = os.path.join(output_gdb, f"{output_fc}_slope")
    aspect_raster = os.path.join(output_gdb, f"{output_fc}_aspect")
    curvature_raster = os.path.join(output_gdb, f"{output_fc}_curvature")
    hillshade_raster = os.path.join(output_gdb, f"{output_fc}_hillshade")

    # Generate slope percent
    arcpy.AddMessage("Calculating slope percent...")
    arcpy.sa.Slope(clipped_dem, "PERCENT_RISE").save(slope_raster)
    arcpy.AddMessage(f"Slope percent raster saved to {slope_raster}")

    # Generate aspect
    arcpy.AddMessage("Calculating aspect...")
    arcpy.sa.Aspect(clipped_dem).save(aspect_raster)
    arcpy.AddMessage(f"Aspect raster saved to {aspect_raster}")

    # Generate slope curvature using curvature analysis
    arcpy.AddMessage("Calculating slope curvature...")
    arcpy.sa.Curvature(clipped_dem).save(curvature_raster)
    arcpy.AddMessage(f"Slope curvature raster saved to {curvature_raster}")

    # Generate hillshade
    arcpy.AddMessage("Generating hillshade...")
    arcpy.sa.Hillshade(clipped_dem, azimuth=315, altitude=45).save(hillshade_raster)
    arcpy.AddMessage(f"Hillshade raster saved to {hillshade_raster}")

    # Extract raster values to points
    arcpy.AddMessage("Extracting raster values to points...")
    extract_rasters = [
        (clipped_dem, "Elevation"),
        (slope_raster, "Slope"),
        (aspect_raster, "Aspect"),
        (curvature_raster, "Curvature")
    ]
    arcpy.sa.ExtractMultiValuesToPoints(output_fc_path, extract_rasters, "NONE")
    arcpy.AddMessage(f"Raster values extracted to points feature class '{output_fc_path}'")

    # Add the rasters to the current map
    aprx = arcpy.mp.ArcGISProject("CURRENT")
    m = aprx.activeMap

    # Add layers to the map
    hillshade_layer = m.addDataFromPath(hillshade_raster)
    if hillshade_layer:
        arcpy.AddMessage("Hillshade raster added to the map.")
    else:
        arcpy.AddError("Failed to add hillshade raster to the map.")

    slope_layer = m.addDataFromPath(slope_raster)
    if slope_layer:
        arcpy.AddMessage("Slope raster added to the map.")
    else:
        arcpy.AddError("Failed to add slope raster to the map.")

    aspect_layer = m.addDataFromPath(aspect_raster)
    if aspect_layer:
        arcpy.AddMessage("Aspect raster added to the map.")
    else:
        arcpy.AddError("Failed to add aspect raster to the map.")

    curvature_layer = m.addDataFromPath(curvature_raster)
    if curvature_layer:
        arcpy.AddMessage("Curvature raster added to the map.")
    else:
        arcpy.AddError("Failed to add curvature raster to the map.")

    elevation_layer = m.addDataFromPath(clipped_dem)
    if elevation_layer:
        arcpy.AddMessage("Elevation raster added to the map.")
    else:
        arcpy.AddError("Failed to add elevation raster to the map.")

    output_fc_layer = m.addDataFromPath(output_fc_path)
    if elevation_layer:
        arcpy.AddMessage("Point Feature Class added to the map.")
    else:
        arcpy.AddError("Failed to add Point Feature Class to the map.")

    # Move layers to the correct order: hillshade at the top, elevation at the bottom
    try:
        if hillshade_layer and slope_layer and aspect_layer and curvature_layer and elevation_layer:
            print("Layers before moving:")
            print(f"Hillshade layer: {hillshade_layer.name}")
            print(f"Slope layer: {slope_layer.name}")
            print(f"Aspect layer: {aspect_layer.name}")
            print(f"Curvature layer: {curvature_layer.name}")
            print(f"Elevation layer: {elevation_layer.name}")
            
            m.moveLayer(hillshade_layer, 1)
            m.moveLayer(slope_layer, 2)
            m.moveLayer(aspect_layer, 3)
            m.moveLayer(curvature_layer, 4)
            m.moveLayer(elevation_layer, 5)
            arcpy.AddMessage("Rasters added to the map with hillshade at the top and elevation at the bottom")
        else:
            arcpy.AddError("Failed to add one or more layers to the map.")
    except Exception as e:
        arcpy.AddError(f"Error moving layers: {str(e)}")
        raise

    # Add the point feature class to the current map
    output_fc_layer = m.addDataFromPath(output_fc_path)
    if output_fc_layer:
        arcpy.AddMessage("Point feature class added to the map.")
        try:
            m.moveLayer(output_fc_layer, "TOP")  # Move point layer to position 0 (top of the stack)
            arcpy.AddMessage("Point layer moved to the top of the map.")
        except Exception as e:
            arcpy.AddError(f"Error moving the point layer to the top: {str(e)}")
            raise
    else:
        arcpy.AddError("Failed to add point feature class to the map.")

    # Print current layer order
    arcpy.AddMessage("Current layer order:")
    for i, layer in enumerate(m.listLayers()):
        arcpy.AddMessage(f"{i}: {layer.name}")

    try:
        # Code block that might raise an error
        arcpy.SomeTool_management(input, output)
    except arcpy.ExecuteError:
        # Handle tool-specific errors
        print(f"Error with tool execution: {arcpy.GetMessages(2)}")
    except Exception as e:
        # Handle unexpected errors
        print(f"Unexpected error: {e}")

    # Clean up temporary datasets
    arcpy.Delete_management(temp_table)
    arcpy.Delete_management(temp_fc_wgs84)
    arcpy.Delete_management(projected_dem)
    arcpy.AddMessage("Temporary datasets removed.")

    # Set the output parameters
    arcpy.SetParameterAsText(2, output_fc_path)
    arcpy.SetParameterAsText(4, clipped_dem)

    # Print messages
    arcpy.AddMessage(f"Point feature class '{output_fc}' created in '{output_gdb}' with spatial reference Alberta 3TM 114 NAD 83")

except Exception as e:
    arcpy.AddError(f"Script failed with error: {str(e)}")
    raise
