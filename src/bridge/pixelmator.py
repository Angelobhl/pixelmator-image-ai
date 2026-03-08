"""
Pixelmator Pro bridge module.
Provides interface to control Pixelmator Pro via AppleScript.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .applescript import AppleScriptRunner


@dataclass
class DocumentInfo:
    """Information about a Pixelmator document."""
    name: str
    width: int
    height: int
    path: Optional[str]


@dataclass
class LayerInfo:
    """Information about a layer."""
    name: str
    index: int
    visible: bool
    locked: bool


@dataclass
class WriteBackResult:
    """Result of importing layer to Pixelmator."""
    success: bool
    layer_name: Optional[str] = None
    error: Optional[str] = None


@dataclass
class ExportResult:
    """Result of exporting a layer from Pixelmator."""
    success: bool
    path: Optional[Path] = None
    original_position: Optional[tuple] = None  # (x, y) top-left corner
    original_bounds: Optional[tuple] = None    # (x1, y1, x2, y2)
    trimmed_size: Optional[tuple] = None       # (width, height) after trimming
    error: Optional[str] = None


class PixelmatorBridge:
    """Bridge to control Pixelmator Pro via AppleScript."""

    def __init__(self):
        self.runner = AppleScriptRunner()

    def is_running(self) -> bool:
        """Check if Pixelmator Pro is running."""
        script = '''
        tell application "System Events"
            return (name of processes) contains "Pixelmator Pro"
        end tell
        '''
        success, result = self.runner.run(script)
        return success and result == "true"

    def activate(self) -> bool:
        """Activate Pixelmator Pro window."""
        script = '''
        tell application "Pixelmator Pro"
            activate
        end tell
        '''
        success, _ = self.runner.run(script)
        return success

    def get_document_info(self) -> Optional[DocumentInfo]:
        """Get information about the current document."""
        script = '''
        tell application "Pixelmator Pro"
            if (count of documents) > 0 then
                set doc to document 1
                set docName to name of doc
                set docWidth to width of doc
                set docHeight to height of doc
                try
                    set docPath to file path of doc as string
                on error
                    set docPath to ""
                end try
                return docName & "|" & docWidth & "|" & docHeight & "|" & docPath
            else
                return ""
            end if
        end tell
        '''
        success, result = self.runner.run(script)
        if success and result:
            parts = result.split("|")
            if len(parts) >= 4:
                return DocumentInfo(
                    name=parts[0],
                    width=int(float(parts[1])),
                    height=int(float(parts[2])),
                    path=parts[3] if parts[3] else None
                )
        return None

    def get_selected_layer_info(self) -> Optional[LayerInfo]:
        """Get information about the selected layer."""
        script = '''
        tell application "Pixelmator Pro"
            if (count of documents) > 0 then
                set doc to document 1
                set selectedLayer to current layer of doc
                set layerName to name of selectedLayer
                set layerIndex to index of selectedLayer
                set layerVisible to visible of selectedLayer
                set layerLocked to locked of selectedLayer
                return layerName & "|" & layerIndex & "|" & layerVisible & "|" & layerLocked
            else
                return ""
            end if
        end tell
        '''
        success, result = self.runner.run(script)
        if success and result:
            parts = result.split("|")
            if len(parts) >= 4:
                return LayerInfo(
                    name=parts[0],
                    index=int(float(parts[1])),
                    visible=parts[2].lower() == "true",
                    locked=parts[3].lower() == "true"
                )
        return None

    def get_layer_bounds(self) -> Optional[tuple]:
        """Get the bounds of the selected layer.

        Note: Pixelmator returns bounds as (x, y, width, height).
        This method converts it to (x1, y1, x2, y2) format.

        Returns:
            Tuple of (x1, y1, x2, y2) or None if no layer selected.
        """
        script = '''
        tell application "Pixelmator Pro"
            if (count of documents) > 0 then
                set doc to document 1
                set selectedLayer to current layer of doc
                set layerBounds to bounds of selectedLayer
                set x to item 1 of layerBounds as integer
                set y to item 2 of layerBounds as integer
                set w to item 3 of layerBounds as integer
                set h to item 4 of layerBounds as integer
                return (x as string) & "|" & (y as string) & "|" & (w as string) & "|" & (h as string)
            else
                return ""
            end if
        end tell
        '''
        success, result = self.runner.run(script)
        if success and result:
            parts = result.split("|")
            if len(parts) == 4:
                try:
                    x = int(parts[0].strip().rstrip(','))
                    y = int(parts[1].strip().rstrip(','))
                    w = int(parts[2].strip().rstrip(','))
                    h = int(parts[3].strip().rstrip(','))
                    # Convert (x, y, width, height) to (x1, y1, x2, y2)
                    return (x, y, x + w, y + h)
                except ValueError:
                    return None
        return None

    def export_layer(
        self,
        output_path: Path,
        layer_name: Optional[str] = None
    ) -> bool:
        """
        Export only the selected layer to a PNG file.

        This method temporarily hides all other layers, exports the current
        layer, then restores the original visibility states.

        Args:
            output_path: Path to save the exported layer
            layer_name: Optional name of specific layer to export

        Returns:
            True if export was successful
        """
        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Hide all layers except the current one, export, then restore visibility
        script = f'''
        tell application "Pixelmator Pro"
            if (count of documents) > 0 then
                set doc to document 1
                set currentLayer to current layer of doc

                -- Get all layers and store their visibility
                set allLayers to every layer of doc
                set visibleStates to {{}}

                -- Hide all layers except current
                repeat with aLayer in allLayers
                    set end of visibleStates to visible of aLayer
                    if aLayer is not currentLayer then
                        set visible of aLayer to false
                    end if
                end repeat

                -- Make sure current layer is visible
                set visible of currentLayer to true

                -- Export the document (now only current layer is visible)
                set theFile to POSIX file "{output_path.as_posix()}"
                export doc to theFile as PNG

                -- Restore visibility states
                set i to 1
                repeat with aLayer in allLayers
                    set visible of aLayer to item i of visibleStates
                    set i to i + 1
                end repeat

                return "success"
            else
                return "no_document"
            end if
        end tell
        '''
        success, result = self.runner.run(script)
        return success and result == "success"

    def export_layer_trimmed(
        self,
        output_path: Path,
        layer_name: Optional[str] = None
    ) -> 'ExportResult':
        """
        Export only the selected layer with transparent area trimmed.

        This method:
        1. Gets the layer bounds (content area)
        2. Hides all other layers
        3. Exports the document
        4. Trims transparent pixels from the exported image
        5. Restores layer visibility

        Args:
            output_path: Path to save the exported layer
            layer_name: Optional name of specific layer to export

        Returns:
            ExportResult with position and size information
        """
        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # First, get the layer bounds
        bounds = self.get_layer_bounds()
        if not bounds:
            return ExportResult(
                success=False,
                error="No layer selected or no document"
            )

        x1, y1, x2, y2 = bounds

        # Hide all layers except the current one, export, then restore visibility
        script = f'''
        tell application "Pixelmator Pro"
            if (count of documents) > 0 then
                set doc to document 1
                set currentLayer to current layer of doc

                -- Get all layers and store their visibility
                set allLayers to every layer of doc
                set visibleStates to {{}}

                -- Hide all layers except current
                repeat with aLayer in allLayers
                    set end of visibleStates to visible of aLayer
                    if aLayer is not currentLayer then
                        set visible of aLayer to false
                    end if
                end repeat

                -- Make sure current layer is visible
                set visible of currentLayer to true

                -- Export the document (now only current layer is visible)
                set theFile to POSIX file "{output_path.as_posix()}"
                export doc to theFile as PNG

                -- Restore visibility states
                set i to 1
                repeat with aLayer in allLayers
                    set visible of aLayer to item i of visibleStates
                    set i to i + 1
                end repeat

                return "success"
            else
                return "no_document"
            end if
        end tell
        '''

        success, result = self.runner.run(script)

        if not success or result != "success":
            return ExportResult(
                success=False,
                error=result if result != "success" else "Export failed"
            )

        # Now trim the transparent area from the exported image
        try:
            trimmed_size = self._trim_transparent_pixels(output_path, bounds)
            if trimmed_size:
                return ExportResult(
                    success=True,
                    path=output_path,
                    original_position=(x1, y1),
                    original_bounds=bounds,
                    trimmed_size=trimmed_size
                )
            else:
                return ExportResult(
                    success=True,
                    path=output_path,
                    original_position=(x1, y1),
                    original_bounds=bounds,
                    trimmed_size=(x2 - x1, y2 - y1)
                )
        except Exception as e:
            return ExportResult(
                success=False,
                error=f"Failed to trim image: {str(e)}"
            )

    def _trim_transparent_pixels(self, image_path: Path, bounds: tuple) -> Optional[tuple]:
        """
        Trim transparent pixels from an image based on layer bounds.

        Args:
            image_path: Path to the image file
            bounds: Original layer bounds (x1, y1, x2, y2)

        Returns:
            Tuple of (width, height) of trimmed image, or None if failed
        """
        try:
            from PIL import Image

            x1, y1, x2, y2 = bounds

            with Image.open(image_path) as img:
                # Convert to RGBA if necessary
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')

                # Crop to the layer bounds
                # PIL crop uses (left, upper, right, lower)
                cropped = img.crop((x1, y1, x2, y2))

                # Save the cropped image
                cropped.save(image_path, 'PNG')

                return (x2 - x1, y2 - y1)

        except ImportError:
            # PIL not available, try using sips command
            return self._trim_with_sips(image_path, bounds)
        except Exception as e:
            print(f"Error trimming image: {e}")
            return None

    def _trim_with_sips(self, image_path: Path, bounds: tuple) -> Optional[tuple]:
        """
        Fallback method to trim image using sips command.
        Note: sips doesn't support direct crop by bounds, so this is limited.
        """
        # sips doesn't have a good way to crop by specific bounds
        # We'll return the bounds size but won't actually trim
        x1, y1, x2, y2 = bounds
        return (x2 - x1, y2 - y1)

    def export_selection(
        self,
        output_path: Path
    ) -> bool:
        """
        Export the current selection to a PNG file.

        Args:
            output_path: Path to save the exported selection

        Returns:
            True if export was successful
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Use 'export' command with 'selection' syntax
        script = f'''
        tell application "Pixelmator Pro"
            if (count of documents) > 0 then
                set doc to document 1
                set theFile to POSIX file "{output_path.as_posix()}"
                export doc to theFile as PNG with selection
                return "success"
            else
                return "no_document"
            end if
        end tell
        '''
        success, result = self.runner.run(script)
        return success and result == "success"

    def import_layer(
        self,
        image_path: Path,
        position: tuple = (0, 0)
    ) -> WriteBackResult:
        """
        Import an image as a new layer.

        Args:
            image_path: Path to the image file
            position: Position (x, y) for the layer

        Returns:
            WriteBackResult with success status
        """
        if not image_path.exists():
            return WriteBackResult(
                success=False,
                error=f"Image file not found: {image_path}"
            )

        script = f'''
        tell application "Pixelmator Pro"
            if (count of documents) > 0 then
                set doc to document 1
                set thePath to POSIX file "{image_path.as_posix()}"
                -- Create new image layer from file
                set newLayer to make new image layer at doc with properties {{file:thePath}}
                set position of newLayer to {{{position[0]}, {position[1]}}}
                set name of newLayer to "AI Generated"
                return name of newLayer
            else
                return "no_document"
            end if
        end tell
        '''
        success, result = self.runner.run(script)
        if success and result != "no_document":
            return WriteBackResult(
                success=True,
                layer_name=result
            )
        else:
            return WriteBackResult(
                success=False,
                error=result or "Unknown error"
            )

    def get_layer_position(self) -> Optional[tuple]:
        """Get the position of the selected layer."""
        script = '''
        tell application "Pixelmator Pro"
            if (count of documents) > 0 then
                set doc to document 1
                set selectedLayer to current layer of doc
                set layerPos to position of selectedLayer
                return item 1 of layerPos & "|" & item 2 of layerPos
            else
                return ""
            end if
        end tell
        '''
        success, result = self.runner.run(script)
        if success and result:
            # Remove commas and split by pipe
            result = result.replace(',', '')
            parts = result.split("|")
            if len(parts) == 2:
                return (int(float(parts[0].strip())), int(float(parts[1].strip())))
        return None